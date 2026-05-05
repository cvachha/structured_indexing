#!/usr/bin/env bash
# Milestone 3 benchmark driver.
# Runs LIPP, DynamicPGM (pareto), and HybridPGMLIPP (pareto) on:
#   - 3 datasets: Facebook, Books, OSMC
#   - 2 mixed workloads per dataset: 90% lookup/10% insert and 10% lookup/90% insert
# Each benchmark repeats 3 times (-r 3) so plots use averaged throughput.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS_DIR="${ROOT_DIR}/results"

# Prefer in-repo build directory, but fall back to writable temp dirs on clusters.
PREFERRED_BUILD_DIR="${ROOT_DIR}/build"
if mkdir -p "${PREFERRED_BUILD_DIR}" 2>/dev/null; then
  BUILD_DIR="${PREFERRED_BUILD_DIR}"
elif [ -n "${SLURM_TMPDIR:-}" ]; then
  BUILD_DIR="${SLURM_TMPDIR}/cos568_build"
  mkdir -p "${BUILD_DIR}"
  echo "Warning: cannot write to ${PREFERRED_BUILD_DIR}; using ${BUILD_DIR}"
elif [ -n "${TMPDIR:-}" ]; then
  BUILD_DIR="${TMPDIR}/cos568_build"
  mkdir -p "${BUILD_DIR}"
  echo "Warning: cannot write to ${PREFERRED_BUILD_DIR}; using ${BUILD_DIR}"
else
  echo "Error: cannot create ${PREFERRED_BUILD_DIR}, and no SLURM_TMPDIR/TMPDIR fallback is available"
  exit 1
fi

echo "ROOT_DIR=${ROOT_DIR}"
echo "BUILD_DIR=${BUILD_DIR}"

cd "${ROOT_DIR}"

echo "========================================="
echo "Building benchmark binaries"
echo "========================================="

cmake -S "${ROOT_DIR}" -B "${BUILD_DIR}" -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS="-O3 -march=native"
cmake --build "${BUILD_DIR}" -j "$(nproc 2>/dev/null || echo 4)"

BENCHMARK="${BUILD_DIR}/benchmark"
GENERATOR="${BUILD_DIR}/generate"

if [ ! -f "${BENCHMARK}" ]; then
  echo "Error: benchmark binary not found at ${BENCHMARK}"
  exit 1
fi
if [ ! -f "${GENERATOR}" ]; then
  echo "Error: generate binary not found at ${GENERATOR}"
  exit 1
fi

mkdir -p "${RESULTS_DIR}"

DATASETS=(
  "fb_100M_public_uint64"
  "books_100M_public_uint64"
  "osmc_100M_public_uint64"
)

run_one() {
  local data="$1"
  local ops="$2"

  echo "  -> LIPP"
  "${BENCHMARK}" "${ROOT_DIR}/data/${data}" "${ROOT_DIR}/data/${ops}" --through --csv --only LIPP -r 3

  echo "  -> DynamicPGM (pareto)"
  "${BENCHMARK}" "${ROOT_DIR}/data/${data}" "${ROOT_DIR}/data/${ops}" --through --csv --only DynamicPGM --pareto -r 3

  echo "  -> HybridPGMLIPP (pareto)"
  "${BENCHMARK}" "${ROOT_DIR}/data/${data}" "${ROOT_DIR}/data/${ops}" --through --csv --only HybridPGMLIPP --pareto -r 3
}

for DATA in "${DATASETS[@]}"; do
  DATA_PATH="${ROOT_DIR}/data/${DATA}"

  if [ ! -f "${DATA_PATH}" ]; then
    echo "Warning: dataset not found at ${DATA_PATH}, skipping ${DATA}"
    continue
  fi

  echo "========================================="
  echo "Generating mixed workloads for ${DATA}"
  echo "========================================="

  "${GENERATOR}" "${ROOT_DIR}/data/${DATA}" 2000000 \
    --insert-ratio 0.1 --negative-lookup-ratio 0.5 --mix

  "${GENERATOR}" "${ROOT_DIR}/data/${DATA}" 2000000 \
    --insert-ratio 0.9 --negative-lookup-ratio 0.5 --mix

  OPS_10I="${DATA}_ops_2M_0.000000rq_0.500000nl_0.100000i_0m_mix"
  OPS_90I="${DATA}_ops_2M_0.000000rq_0.500000nl_0.900000i_0m_mix"

  echo "--- ${DATA}: 90% lookup / 10% insert ---"
  run_one "${DATA}" "${OPS_10I}"

  echo "--- ${DATA}: 10% lookup / 90% insert ---"
  run_one "${DATA}" "${OPS_90I}"
done

echo "========================================="
echo "Normalizing CSV headers"
echo "========================================="

MIX_HEADER="index_name,build_time_ns1,build_time_ns2,build_time_ns3,\
index_size_bytes,mixed_throughput_mops1,mixed_throughput_mops2,mixed_throughput_mops3,\
search_method,pgm_error,flush_threshold,flush_batch,max_flush_threshold,min_flush_threshold"

for FILE in "${ROOT_DIR}/results/"*mix*_results_table.csv; do
  [ -f "${FILE}" ] || continue

  # Drop existing header line if present.
  if head -n 1 "${FILE}" | grep -q "index_name"; then
    sed -i '1d' "${FILE}"
  fi

  sed -i "1s/^/${MIX_HEADER}\n/" "${FILE}"
  echo "Header set for $(basename "${FILE}")"
done

echo "========================================="
echo "Task 3 benchmarking complete."
echo "Generate plots with:"
echo "  python3 scripts/milestone3_plot.py"
echo "========================================="
