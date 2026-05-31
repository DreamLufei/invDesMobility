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

if [[ -z "${MODEL_PATH:-}" ]]; then
  MODEL_PATH="${DIFFCSP_FINETUNED_DIR}"
fi

if [[ -z "${MODEL_PATH}" || ! -d "${MODEL_PATH}" ]]; then
  echo "[03_generate_multigpu] MODEL_PATH is missing or invalid: ${MODEL_PATH:-<empty>}" >&2
  exit 1
fi

TOTAL_SAMPLES="${TOTAL_SAMPLES:-1000}"
SAMPLES_PER_JOB="${SAMPLES_PER_JOB:-1000}"
NUM_BATCHES_TO_SAMPLES="${NUM_BATCHES_TO_SAMPLES:-1}"
GPU_LIST_RAW="${GPU_LIST:-0,1,2,3}"
CONVERT_TO_CIF="${CONVERT_TO_CIF:-1}"
LABEL_PREFIX="${LABEL_PREFIX:-gen}"
DATASET="${DATASET:-${DIFFCSP_DATASET_NAME}}"
MODEL_BASENAME="$(basename "${MODEL_PATH}")"
RUN_ID="${RUN_ID:-$(date +%Y%m%d)__generated_${TOTAL_SAMPLES}_structures__from_${MODEL_BASENAME}}"
RUN_ROOT="${RUN_ROOT:-${RUNS_ROOT}/${RUN_ID}}"
PT_OUTPUT_DIR="${PT_OUTPUT_DIR:-${RUN_ROOT}/03_generate_structures/generated_pt}"
CIF_OUTPUT_DIR="${CIF_OUTPUT_DIR:-${RUN_ROOT}/03_generate_structures/generated_cif}"
RUN_LOG_DIR="${RUN_LOG_DIR:-${LOGS_BY_RUN_ROOT}/${RUN_ID}}"
MASTER_LOG="${RUN_LOG_DIR}/03_generate_multigpu.log"
PT_TO_CIF_LOG="${RUN_LOG_DIR}/04_pt_to_cif_bad_samples.log"

mkdir -p "${PT_OUTPUT_DIR}" "${CIF_OUTPUT_DIR}" "${RUN_LOG_DIR}"

GPU_LIST_NORMALIZED="${GPU_LIST_RAW//,/ }"
read -r -a GPUS <<< "${GPU_LIST_NORMALIZED}"
if [[ "${#GPUS[@]}" -eq 0 ]]; then
  echo "[03_generate_multigpu] GPU_LIST is empty" >&2
  exit 1
fi

if (( TOTAL_SAMPLES <= 0 )); then
  echo "[03_generate_multigpu] TOTAL_SAMPLES must be > 0" >&2
  exit 1
fi

if (( SAMPLES_PER_JOB <= 0 )); then
  echo "[03_generate_multigpu] SAMPLES_PER_JOB must be > 0" >&2
  exit 1
fi

if (( TOTAL_SAMPLES % SAMPLES_PER_JOB != 0 )); then
  echo "[03_generate_multigpu] TOTAL_SAMPLES must be divisible by SAMPLES_PER_JOB" >&2
  exit 1
fi

JOB_COUNT=$((TOTAL_SAMPLES / SAMPLES_PER_JOB))
echo "[03_generate_multigpu] run_id=${RUN_ID}" | tee "${MASTER_LOG}"
echo "[03_generate_multigpu] total_samples=${TOTAL_SAMPLES} samples_per_job=${SAMPLES_PER_JOB} job_count=${JOB_COUNT} gpus=${GPU_LIST_RAW}" | tee -a "${MASTER_LOG}"

run_worker() {
  local gpu="$1"
  local offset="$2"
  local stride="$3"
  local worker_log="${RUN_LOG_DIR}/03_generate_gpu${gpu}.log"
  local idx
  cd "${DIFFCSP_ROOT}"
  for idx in $(seq $((offset + 1)) "${stride}" "${JOB_COUNT}"); do
    local label
    label="$(printf "%s_part%03d" "${LABEL_PREFIX}" "${idx}")"
    local tmp_pt
    local dst_pt
    tmp_pt="${MODEL_PATH}/eval_gen_${label}.pt"
    dst_pt="${PT_OUTPUT_DIR}/eval_gen_${label}.pt"
    if [[ -f "${dst_pt}" ]]; then
      echo "[03_generate_multigpu] gpu=${gpu} label=${label} already exists, skipping" | tee -a "${worker_log}" "${MASTER_LOG}"
      continue
    fi

    echo "[03_generate_multigpu] gpu=${gpu} label=${label} start $(date --iso-8601=seconds)" | tee -a "${worker_log}" "${MASTER_LOG}"
    CUDA_VISIBLE_DEVICES="${gpu}" python scripts/generation.py \
      --model_path "${MODEL_PATH}" \
      --dataset "${DATASET}" \
      --batch_size "${SAMPLES_PER_JOB}" \
      --num_batches_to_samples "${NUM_BATCHES_TO_SAMPLES}" \
      --label "${label}" 2>&1 | tee -a "${worker_log}"

    if [[ ! -f "${tmp_pt}" ]]; then
      echo "[03_generate_multigpu] gpu=${gpu} label=${label} missing output: ${tmp_pt}" | tee -a "${worker_log}" "${MASTER_LOG}"
      return 1
    fi

    mv -f "${tmp_pt}" "${dst_pt}"
    echo "[03_generate_multigpu] gpu=${gpu} label=${label} moved -> ${dst_pt}" | tee -a "${worker_log}" "${MASTER_LOG}"
    echo "[03_generate_multigpu] gpu=${gpu} label=${label} done $(date --iso-8601=seconds)" | tee -a "${worker_log}" "${MASTER_LOG}"
  done
}

pids=()
for gpu_idx in "${!GPUS[@]}"; do
  run_worker "${GPUS[$gpu_idx]}" "${gpu_idx}" "${#GPUS[@]}" &
  pids+=("$!")
done

job_failed=0
for pid in "${pids[@]}"; do
  if ! wait "${pid}"; then
    job_failed=1
  fi
done

if (( job_failed != 0 )); then
  echo "[03_generate_multigpu] one or more generation workers failed" | tee -a "${MASTER_LOG}"
  exit 1
fi

if [[ "${CONVERT_TO_CIF}" == "1" ]]; then
  python "${SCRIPT_DIR}/pt_to_cif.py" \
    --input_dir "${PT_OUTPUT_DIR}" \
    --output_dir "${CIF_OUTPUT_DIR}" \
    --log_path "${PT_TO_CIF_LOG}" 2>&1 | tee -a "${MASTER_LOG}"
fi

python - "${RUN_ID}" "${RUN_ROOT}" "${PT_OUTPUT_DIR}" "${CIF_OUTPUT_DIR}" "${RUN_LOG_DIR}" "${MODEL_PATH}" "${TOTAL_SAMPLES}" "${SAMPLES_PER_JOB}" "${JOB_COUNT}" "${GPU_LIST_RAW}" "${DATASET}" "${CONVERT_TO_CIF}" <<'PY'
import json
import sys
from pathlib import Path

run_id = sys.argv[1]
run_root = Path(sys.argv[2])
manifest = {
    "run_id": run_id,
    "source_model_dir": sys.argv[6],
    "generated_pt_dir": sys.argv[3],
    "generated_cif_dir": sys.argv[4],
    "run_log_dir": sys.argv[5],
    "generation_count": int(sys.argv[7]),
    "generation_batch_size": int(sys.argv[8]),
    "generation_batches": int(sys.argv[9]),
    "gpu_list": sys.argv[10],
    "dataset": sys.argv[11],
    "convert_to_cif": sys.argv[12] == "1",
}
(run_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
PY

echo "[03_generate_multigpu] completed: ${RUN_ROOT}" | tee -a "${MASTER_LOG}"
