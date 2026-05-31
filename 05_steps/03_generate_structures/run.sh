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

CONDA_BASE="${CONDA_BASE:-$(conda info --base)}"
source "${CONDA_BASE}/etc/profile.d/conda.sh"
conda activate diffcsp-gen
source "${PROJECT_ROOT}/diffcsp_runtime.sh"

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_generated_structures}"
RUN_ROOT="${RUN_ROOT:-${RUNS_ROOT}/${RUN_ID}}"
DIFF_ROOT="${DIFFCSP_ROOT}"
OUTPUT_DIR="${OUTPUT_DIR:-${RUN_ROOT}/03_generate_structures/generated_pt}"
LOG_PATH="${LOG_PATH:-${LOGS_ROOT}/03_generate_structures/${RUN_ID}__generate.log}"
COUNT="${COUNT:-2}"
BATCH_SIZE="${BATCH_SIZE:-2}"
NUM_BATCHES_TO_SAMPLES="${NUM_BATCHES_TO_SAMPLES:-1}"
DATASET="${DATASET:-${DIFFCSP_DATASET_NAME}}"

mkdir -p "${OUTPUT_DIR}" "$(dirname "${LOG_PATH}")"

if [[ -z "${MODEL_PATH:-}" ]]; then
  MODEL_PATH="${DIFFCSP_FINETUNED_DIR}"
fi

if [[ -z "${MODEL_PATH}" || ! -d "${MODEL_PATH}" ]]; then
  echo "[04_generate_small] MODEL_PATH is missing or invalid: ${MODEL_PATH:-<empty>}" | tee "${LOG_PATH}"
  exit 1
fi

cd "${DIFF_ROOT}"
for idx in $(seq 1 "${COUNT}"); do
  label="${LABEL_PREFIX:-mobility2d_hq280_run}_${idx}"
  python scripts/generation.py \
    --model_path "${MODEL_PATH}" \
    --dataset "${DATASET}" \
    --batch_size "${BATCH_SIZE}" \
    --num_batches_to_samples "${NUM_BATCHES_TO_SAMPLES}" \
    --label "${label}" 2>&1 | tee -a "${LOG_PATH}"

  src_file="${MODEL_PATH}/eval_gen_${label}.pt"
  dst_file="${OUTPUT_DIR}/eval_gen_${label}.pt"
  if [[ -f "${src_file}" ]]; then
    mv -f "${src_file}" "${dst_file}"
    echo "[04_generate_small] moved ${src_file} -> ${dst_file}" | tee -a "${LOG_PATH}"
  else
    echo "[04_generate_small] expected output missing: ${src_file}" | tee -a "${LOG_PATH}"
    exit 1
  fi
done
