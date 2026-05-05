#ifndef TLI_HYBRID_PGM_LIPP_H
#define TLI_HYBRID_PGM_LIPP_H

#include <algorithm>
#include <condition_variable>
#include <cstdlib>
#include <mutex>
#include <shared_mutex>
#include <thread>
#include <vector>

#include "../util.h"
#include "base.h"
#include "pgm_index_dynamic.hpp"
#include "./lipp/src/core/lipp.h"

// HybridPGMLIPP: async double-buffered flushing from Dynamic PGM to LIPP.
//
// Design:
//   active_pgm_       <- all new insertions land here
//   pending_pgm_      <- sealed active buffer waiting while a flush is running
//   flushing_snapshot_<- sorted vector snapshot being drained into LIPP by background worker
//   lipp_             <- main index; receives all flushed keys
//
// state_mu_ is a shared_mutex so concurrent lookups (shared lock) never block
// each other; only inserts and buffer rotations need exclusive access.
// condition_variable_any is required because state_mu_ is a shared_mutex.

template <class KeyType, class SearchClass, size_t pgm_error>
class HybridPGMLIPP : public Competitor<KeyType, SearchClass> {
  using PGMType =
      DynamicPGMIndex<KeyType, uint64_t, SearchClass,
                      PGMIndex<KeyType, SearchClass, pgm_error, 16>>;
  using KVPair = std::pair<KeyType, uint64_t>;

 public:
  HybridPGMLIPP(const std::vector<int>& params)
      : flush_threshold_ratio_(0.05),
        flush_batch_size_(512),
        min_flush_threshold_(1024),
        max_flush_threshold_(1 << 16) {
    if (!params.empty()) flush_threshold_ratio_ = params[0] / 100.0;
    if (params.size() > 1 && params[1] > 0)
      flush_batch_size_ = static_cast<size_t>(params[1]);
    if (params.size() > 2 && params[2] > 0)
      max_flush_threshold_ = static_cast<size_t>(params[2]);
    if (params.size() > 3 && params[3] > 0)
      min_flush_threshold_ = static_cast<size_t>(params[3]);
  }

  ~HybridPGMLIPP() { StopFlushWorker(); }

  HybridPGMLIPP(const HybridPGMLIPP&) = delete;
  HybridPGMLIPP& operator=(const HybridPGMLIPP&) = delete;
  HybridPGMLIPP(HybridPGMLIPP&&) = delete;
  HybridPGMLIPP& operator=(HybridPGMLIPP&&) = delete;

  uint64_t Build(const std::vector<KeyValue<KeyType>>& data, size_t num_threads) {
    std::vector<KVPair> loading_data;
    loading_data.reserve(data.size());
    for (const auto& itm : data)
      loading_data.emplace_back(itm.key, itm.value);

    {
      std::unique_lock<std::shared_mutex> state_lock(state_mu_);
      total_keys_ = data.size();
      flush_threshold_ = ComputeFlushThreshold(total_keys_);
    }

    uint64_t build_time = util::timing([&] {
      std::unique_lock<std::shared_mutex> lipp_lock(lipp_mu_);
      lipp_.bulk_load(loading_data.data(), loading_data.size());
    });

    StartFlushWorker();
    return build_time;
  }

  size_t EqualityLookup(const KeyType& lookup_key, uint32_t thread_id) const {
    uint64_t value = 0;
    if (FindInBuffers(lookup_key, value)) return value;

    std::shared_lock<std::shared_mutex> lipp_lock(lipp_mu_);
    if (!lipp_.find(lookup_key, value)) return util::NOT_FOUND;
    return value;
  }

  uint64_t RangeQuery(const KeyType& lower_key, const KeyType& upper_key,
                      uint32_t thread_id) const {
    uint64_t result = 0;
    {
      std::shared_lock<std::shared_mutex> state_lock(state_mu_);
      for (auto it = active_pgm_.lower_bound(lower_key);
           it != active_pgm_.end() && it->key() <= upper_key; ++it)
        result += it->value();

      for (auto it = pending_pgm_.lower_bound(lower_key);
           it != pending_pgm_.end() && it->key() <= upper_key; ++it)
        result += it->value();

      if (!flushing_snapshot_.empty()) {
        auto lo = std::lower_bound(
            flushing_snapshot_.begin(), flushing_snapshot_.end(),
            KVPair{lower_key, 0},
            [](const KVPair& a, const KVPair& b) { return a.first < b.first; });
        for (; lo != flushing_snapshot_.end() && lo->first <= upper_key; ++lo)
          result += lo->second;
      }
    }

    std::shared_lock<std::shared_mutex> lipp_lock(lipp_mu_);
    auto it = lipp_.lower_bound(lower_key);
    while (it != lipp_.end() && it->comp.data.key <= upper_key) {
      result += it->comp.data.value;
      ++it;
    }
    return result;
  }

  void Insert(const KeyValue<KeyType>& data, uint32_t thread_id) {
    {
      std::unique_lock<std::shared_mutex> state_lock(state_mu_);
      active_pgm_.insert(data.key, data.value);
      ++active_pgm_size_;
      ++total_keys_;

      if (active_pgm_size_ >= flush_threshold_)
        TrySealActiveBufferLocked();
    }
    flush_cv_.notify_one();
  }

  std::string name() const { return "HybridPGMLIPP"; }

  std::size_t size() const {
    std::size_t total = 0;
    {
      std::shared_lock<std::shared_mutex> state_lock(state_mu_);
      total = active_pgm_.size_in_bytes() + pending_pgm_.size_in_bytes() +
              flushing_snapshot_.capacity() * sizeof(KVPair);
    }
    {
      std::shared_lock<std::shared_mutex> lipp_lock(lipp_mu_);
      total += lipp_.index_size();
    }
    return total;
  }

  bool applicable(bool unique, bool range_query, bool insert, bool multithread,
                  const std::string& ops_filename) const {
    return unique && !range_query && !multithread &&
           SearchClass::name() != "LinearAVX";
  }

  std::vector<std::string> variants() const {
    return {
        SearchClass::name(),
        std::to_string(pgm_error),
        std::to_string(static_cast<int>(flush_threshold_ratio_ * 100)),
        std::to_string(flush_batch_size_),
        std::to_string(max_flush_threshold_),
        std::to_string(min_flush_threshold_),
    };
  }

 private:
  size_t ComputeFlushThreshold(size_t n) const {
    const size_t r =
        static_cast<size_t>(static_cast<double>(n) * flush_threshold_ratio_);
    return std::max(min_flush_threshold_, std::min(max_flush_threshold_, r));
  }

  // Shared-lock read: check all three buffers before falling through to LIPP.
  bool FindInBuffers(const KeyType& key, uint64_t& value) const {
    std::shared_lock<std::shared_mutex> state_lock(state_mu_);

    auto it = active_pgm_.find(key);
    if (it != active_pgm_.end()) { value = it->value(); return true; }

    it = pending_pgm_.find(key);
    if (it != pending_pgm_.end()) { value = it->value(); return true; }

    if (!flushing_snapshot_.empty()) {
      // Binary search on sorted snapshot — cache-friendly and lock-free to write.
      auto lo = std::lower_bound(
          flushing_snapshot_.begin(), flushing_snapshot_.end(),
          KVPair{key, 0},
          [](const KVPair& a, const KVPair& b) { return a.first < b.first; });
      if (lo != flushing_snapshot_.end() && lo->first == key) {
        value = lo->second;
        return true;
      }
    }
    return false;
  }

  // Snapshot a PGM buffer into a sorted vector (PGM iterates in key order).
  // Called only under exclusive lock so dst is stable after this returns.
  void SnapshotPGM(const PGMType& src, std::vector<KVPair>& dst,
                   size_t hint) const {
    dst.clear();
    dst.reserve(hint);
    for (auto it = src.begin(); it != src.end(); ++it)
      dst.emplace_back(it->key(), it->value());
    // dst is already sorted because DynamicPGM iterates in ascending key order.
  }

  // Called under exclusive lock from Insert (or StopFlushWorker).
  // Seals active_pgm_ into flushing_snapshot_ or pending_pgm_.
  // If both destinations are occupied the active buffer keeps growing.
  void TrySealActiveBufferLocked() const {
    if (flushing_snapshot_.empty() && pending_pgm_size_ == 0) {
      SnapshotPGM(active_pgm_, flushing_snapshot_, active_pgm_size_);
      flush_offset_ = 0;
      active_pgm_ = PGMType{};
      active_pgm_size_ = 0;
    } else if (pending_pgm_size_ == 0) {
      pending_pgm_ = std::move(active_pgm_);
      pending_pgm_size_ = active_pgm_size_;
      active_pgm_ = PGMType{};
      active_pgm_size_ = 0;
    }
    // Both occupied: active grows; threshold is bumped so we don't busy-loop.
    flush_threshold_ = ComputeFlushThreshold(total_keys_);
  }

  // Called under exclusive lock from FlushWorkerMain.
  void PromotePendingToFlushingLocked() const {
    SnapshotPGM(pending_pgm_, flushing_snapshot_, pending_pgm_size_);
    flush_offset_ = 0;
    pending_pgm_ = PGMType{};
    pending_pgm_size_ = 0;
  }

  void StartFlushWorker() {
    std::unique_lock<std::shared_mutex> lock(state_mu_);
    if (worker_started_) return;
    stop_worker_ = false;
    worker_started_ = true;
    flush_worker_ = std::thread([this] { FlushWorkerMain(); });
  }

  void StopFlushWorker() {
    {
      std::unique_lock<std::shared_mutex> lock(state_mu_);
      if (!worker_started_) return;
      stop_worker_ = true;
    }
    flush_cv_.notify_all();
    if (flush_worker_.joinable()) flush_worker_.join();
    worker_started_ = false;
  }

  void FlushWorkerMain() const {
    while (true) {
      std::vector<KVPair> batch;
      bool reached_end = false;
      batch.reserve(flush_batch_size_);

      {
        std::unique_lock<std::shared_mutex> state_lock(state_mu_);
        // condition_variable_any works with unique_lock<shared_mutex>.
        flush_cv_.wait(state_lock, [&] {
          return stop_worker_ || !flushing_snapshot_.empty() ||
                 pending_pgm_size_ > 0;
        });

        if (flushing_snapshot_.empty() && pending_pgm_size_ > 0)
          PromotePendingToFlushingLocked();

        if (stop_worker_ && flushing_snapshot_.empty() &&
            pending_pgm_size_ == 0)
          break;

        // Collect next batch from the snapshot vector (fast contiguous copy).
        const size_t end = std::min(flush_offset_ + flush_batch_size_,
                                    flushing_snapshot_.size());
        batch.assign(flushing_snapshot_.begin() + flush_offset_,
                     flushing_snapshot_.begin() + end);
        flush_offset_ = end;
        reached_end = (flush_offset_ >= flushing_snapshot_.size());
      }
      // state_mu_ released — concurrent lookups can proceed here.

      if (batch.empty()) continue;

      {
        std::unique_lock<std::shared_mutex> lipp_lock(lipp_mu_);
        for (const auto& kv : batch)
          lipp_.insert(kv.first, kv.second);
      }

      if (reached_end) {
        std::unique_lock<std::shared_mutex> state_lock(state_mu_);
        // Re-check: a concurrent insert may have created a new snapshot.
        if (flush_offset_ >= flushing_snapshot_.size()) {
          flushing_snapshot_.clear();
          flushing_snapshot_.shrink_to_fit();
          flush_offset_ = 0;
          if (pending_pgm_size_ > 0)
            PromotePendingToFlushingLocked();
        }
      }
    }
  }

  mutable PGMType active_pgm_;
  mutable PGMType pending_pgm_;
  mutable std::vector<KVPair> flushing_snapshot_;
  mutable size_t flush_offset_ = 0;
  mutable LIPP<KeyType, uint64_t> lipp_;

  mutable size_t active_pgm_size_ = 0;
  mutable size_t pending_pgm_size_ = 0;
  mutable size_t total_keys_ = 0;
  mutable size_t flush_threshold_ = 0;

  // shared_mutex: shared for reads (FindInBuffers, size, RangeQuery),
  //               exclusive for writes (Insert, buffer rotations, FlushWorker).
  mutable std::shared_mutex state_mu_;
  mutable std::condition_variable_any flush_cv_;
  mutable std::shared_mutex lipp_mu_;
  mutable std::thread flush_worker_;
  mutable bool stop_worker_ = false;
  bool worker_started_ = false;

  double flush_threshold_ratio_;
  size_t flush_batch_size_;
  size_t min_flush_threshold_;
  size_t max_flush_threshold_;
};

#endif  // TLI_HYBRID_PGM_LIPP_H
