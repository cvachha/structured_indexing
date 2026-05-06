#ifndef TLI_HYBRID_PGM_LIPP_H
#define TLI_HYBRID_PGM_LIPP_H

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <vector>

#include "../util.h"
#include "base.h"
#include "pgm_index_dynamic.hpp"
#include "./lipp/src/core/lipp.h"

template <class KeyType, class SearchClass, size_t pgm_error>
class HybridPGMLIPP : public Competitor<KeyType, SearchClass> {
 public:
  HybridPGMLIPP(const std::vector<int>& params) 
    : flush_threshold_ratio_(0.05) {  // Default 5% threshold
    if (params.size() > 0) {
      flush_threshold_ratio_ = params[0] / 100.0;  // Convert from percentage
    }
  }

  uint64_t Build(const std::vector<KeyValue<KeyType>>& data, size_t num_threads) {
    std::vector<std::pair<KeyType, uint64_t>> loading_data;
    loading_data.reserve(data.size());
    for (const auto& itm : data) {
      loading_data.emplace_back(itm.key, itm.value);
    }

    total_keys_ = data.size();
    flush_threshold_ = static_cast<size_t>(total_keys_ * flush_threshold_ratio_);

    // Bulk load data into LIPP
    uint64_t build_time = util::timing([&] { 
      lipp_.bulk_load(loading_data.data(), loading_data.size()); 
    });

    return build_time;
  }

  size_t EqualityLookup(const KeyType& lookup_key, uint32_t thread_id) const {
    // First check DPGM (smaller, newer data)
    auto it = pgm_.find(lookup_key);
    if (it != pgm_.end()) {
      return it->value();
    }

    // If not found in DPGM, check LIPP
    uint64_t value;
    if (!lipp_.find(lookup_key, value)) {
      return util::NOT_FOUND;
    }
    return value;
  }

  uint64_t RangeQuery(const KeyType& lower_key, const KeyType& upper_key, uint32_t thread_id) const {
    uint64_t result = 0;
    
    // Query DPGM
    auto it_pgm = pgm_.lower_bound(lower_key);
    while (it_pgm != pgm_.end() && it_pgm->key() <= upper_key) {
      result += it_pgm->value();
      ++it_pgm;
    }

    // Query LIPP
    auto it_lipp = lipp_.lower_bound(lower_key);
    while (it_lipp != lipp_.end() && it_lipp->comp.data.key <= upper_key) {
      result += it_lipp->comp.data.value;
      ++it_lipp;
    }

    return result;
  }

  void Insert(const KeyValue<KeyType>& data, uint32_t thread_id) {
    // Insert into DPGM
    // Naive implementation: no flushing, DPGM grows indefinitely
    pgm_.insert(data.key, data.value);
    pgm_size_++;
    
    // Note: Flush disabled for naive milestone implementation
    // In a production version, implement batch flushing to LIPP
  }

  std::string name() const { return "HybridPGMLIPP"; }

  std::size_t size() const { 
    return pgm_.size_in_bytes() + lipp_.index_size(); 
  }

  bool applicable(bool unique, bool range_query, bool insert, bool multithread, const std::string& ops_filename) const {
    std::string search_name = SearchClass::name();
    // Both LIPP and DPGM require unique keys and don't support multithreading
    return unique && !multithread && search_name != "LinearAVX";
  }

  std::vector<std::string> variants() const { 
    std::vector<std::string> vec;
    vec.push_back(SearchClass::name());
    vec.push_back(std::to_string(pgm_error));
    vec.push_back(std::to_string(static_cast<int>(flush_threshold_ratio_ * 100)));
    return vec;
  }

 private:
  // FlushDPGMToLIPP() removed for milestone naive implementation
  // Reason: DynamicPGMIndex iterator has compatibility issues
  // Future improvement: Implement batch flush using bulk load or range scan

  DynamicPGMIndex<KeyType, uint64_t, SearchClass, PGMIndex<KeyType, SearchClass, pgm_error, 16>> pgm_;
  LIPP<KeyType, uint64_t> lipp_;
  size_t pgm_size_ = 0;
  size_t total_keys_ = 0;
  size_t flush_threshold_ = 0;
  double flush_threshold_ratio_;
};

#endif  // TLI_HYBRID_PGM_LIPP_H
