#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT_DIR}/00_project/paths.sh"
if [[ -f "${SCRIPT_DIR}/config.env" ]]; then
  # shellcheck disable=SC1090
  source "${SCRIPT_DIR}/config.env"
fi

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_top10_export}"
RANKED_CSV="${RANKED_CSV:-${RUNS_ROOT}/${RUN_ID}/04_alignn_mobility_rank/mobility_ranked_candidates.csv}"
OUTPUT_DIR="${OUTPUT_DIR:-${RUNS_ROOT}/${RUN_ID}/05_top10_cif}"
SUMMARY_CSV="${SUMMARY_CSV:-${OUTPUT_DIR}/top10_candidates.csv}"
TOP_K="${TOP_K:-10}"
LOG_PATH="${LOG_PATH:-${LOGS_ROOT}/07_export_top10_cif/${RUN_ID}__top10.log}"

mkdir -p "${OUTPUT_DIR}" "$(dirname "${LOG_PATH}")"

python "${SCRIPT_DIR}/collect_topk_cif.py" \
  --ranked_csv "${RANKED_CSV}" \
  --output_dir "${OUTPUT_DIR}" \
  --summary_csv "${SUMMARY_CSV}" \
  --top_k "${TOP_K}" 2>&1 | tee "${LOG_PATH}"
