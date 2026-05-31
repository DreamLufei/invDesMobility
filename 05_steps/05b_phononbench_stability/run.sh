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

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_phononbench_stability}"
PHONONBENCH_ENV_NAME="${PHONONBENCH_ENV_NAME:-mattersim}"
PHONONBENCH_MODEL="${PHONONBENCH_MODEL:-mattersim-v1}"
PHONONBENCH_INPUT_CIF_DIR="${PHONONBENCH_INPUT_CIF_DIR:-${RUNS_ROOT}/${RUN_ID}/05_candidates_after_formation/formation_selected_cif}"
PHONONBENCH_PHONOPY_INPUT_DIR="${PHONONBENCH_PHONOPY_INPUT_DIR:-${RUNS_ROOT}/${RUN_ID}/06_phononbench_stability/phonopy_inputs}"
PHONONBENCH_OUTPUT_DIR="${PHONONBENCH_OUTPUT_DIR:-${RUNS_ROOT}/${RUN_ID}/06_phononbench_stability/phonon_output}"
PHONONBENCH_RELAXED_DIR="${PHONONBENCH_RELAXED_DIR:-${RUNS_ROOT}/${RUN_ID}/06_phononbench_stability/relaxed}"
PHONONBENCH_ALL_OUTPUT_CSV="${PHONONBENCH_ALL_OUTPUT_CSV:-${RUNS_ROOT}/${RUN_ID}/06_phononbench_stability/phonon_stability_all.csv}"
PHONONBENCH_STABLE_OUTPUT_CSV="${PHONONBENCH_STABLE_OUTPUT_CSV:-${RUNS_ROOT}/${RUN_ID}/06_phononbench_stability/phonon_stable_candidates.csv}"
PHONONBENCH_STABLE_CIF_DIR="${PHONONBENCH_STABLE_CIF_DIR:-${RUNS_ROOT}/${RUN_ID}/06_phononbench_stability/stable_relaxed_cif}"
PHONONBENCH_SUMMARY_JSON="${PHONONBENCH_SUMMARY_JSON:-${RUNS_ROOT}/${RUN_ID}/06_phononbench_stability/phonon_stability_summary.json}"
PHONONBENCH_LOG_PATH="${PHONONBENCH_LOG_PATH:-${LOGS_ROOT}/05b_phononbench_stability/${RUN_ID}__phononbench.log}"
PHONONBENCH_DIM="${PHONONBENCH_DIM:-2 2 2}"
PHONONBENCH_GPU_LIST="${PHONONBENCH_GPU_LIST:-0}"
PHONONBENCH_SUBPARTS_PER_GPU="${PHONONBENCH_SUBPARTS_PER_GPU:-1}"
PHONONBENCH_IMAG_THRESHOLD="${PHONONBENCH_IMAG_THRESHOLD:-0.1}"

mkdir -p \
  "$(dirname "${PHONONBENCH_ALL_OUTPUT_CSV}")" \
  "$(dirname "${PHONONBENCH_LOG_PATH}")" \
  "${PHONONBENCH_PHONOPY_INPUT_DIR}" \
  "${PHONONBENCH_OUTPUT_DIR}" \
  "${PHONONBENCH_RELAXED_DIR}" \
  "${PHONONBENCH_STABLE_CIF_DIR}"

if [[ ! -d "${PHONONBENCH_ROOT}" ]]; then
  echo "[05b_phononbench_stability] missing vendored PhononBench code: ${PHONONBENCH_ROOT}" | tee "${PHONONBENCH_LOG_PATH}"
  exit 2
fi

if [[ ! -d "${PHONONBENCH_INPUT_CIF_DIR}" ]]; then
  echo "[05b_phononbench_stability] missing input CIF dir: ${PHONONBENCH_INPUT_CIF_DIR}" | tee "${PHONONBENCH_LOG_PATH}"
  exit 2
fi

CONDA_BASE="${CONDA_BASE:-$(conda info --base)}"
# shellcheck disable=SC1091
source "${CONDA_BASE}/etc/profile.d/conda.sh"
conda activate "${PHONONBENCH_ENV_NAME}"

read -r -a PHONON_DIM_ARR <<< "${PHONONBENCH_DIM}"
GPU_LIST_NORMALIZED="${PHONONBENCH_GPU_LIST//,/ }"
read -r -a PHYS_GPUS <<< "${GPU_LIST_NORMALIZED}"

if [[ "${#PHONON_DIM_ARR[@]}" -ne 3 ]]; then
  echo "[05b_phononbench_stability] PHONONBENCH_DIM must contain exactly 3 integers" | tee "${PHONONBENCH_LOG_PATH}"
  exit 2
fi

if [[ "${#PHYS_GPUS[@]}" -eq 0 ]]; then
  echo "[05b_phononbench_stability] PHONONBENCH_GPU_LIST is empty" | tee "${PHONONBENCH_LOG_PATH}"
  exit 2
fi

python "${PHONONBENCH_ROOT}/batch_prepare_phonopy_input.py" \
  --input_dir "${PHONONBENCH_INPUT_CIF_DIR}" \
  --dim "${PHONON_DIM_ARR[@]}" \
  --out "${PHONONBENCH_PHONOPY_INPUT_DIR}" 2>&1 | tee "${PHONONBENCH_LOG_PATH}"

JOB_LOG_DIR="$(dirname "${PHONONBENCH_LOG_PATH}")/$(basename "${PHONONBENCH_LOG_PATH}" .log)__jobs"
mkdir -p "${JOB_LOG_DIR}"

pids=()
logic_gpu_total="${#PHYS_GPUS[@]}"
for idx in "${!PHYS_GPUS[@]}"; do
  phys_gpu="${PHYS_GPUS[$idx]}"
  logic_gpu="${idx}"
  for subpart_index in $(seq 0 $((PHONONBENCH_SUBPARTS_PER_GPU - 1))); do
    job_log="${JOB_LOG_DIR}/gpu${phys_gpu}_part${subpart_index}.log"
    echo "[05b_phononbench_stability] launching GPU ${phys_gpu}, part ${subpart_index}" | tee -a "${PHONONBENCH_LOG_PATH}"
    CUDA_VISIBLE_DEVICES="${phys_gpu}" \
      python -u "${PHONONBENCH_ROOT}/phonon_multi_gpu_run.py" \
        --ref "${PHONONBENCH_PHONOPY_INPUT_DIR}" \
        --dest "${PHONONBENCH_OUTPUT_DIR}" \
        --relaxedDest "${PHONONBENCH_RELAXED_DIR}" \
        --model "${PHONONBENCH_MODEL}" \
        --imag_threshold "${PHONONBENCH_IMAG_THRESHOLD}" \
        --gpu_index "${logic_gpu}" \
        --subpart_index "${subpart_index}" \
        --total_gpus "${logic_gpu_total}" \
        --subparts_per_gpu "${PHONONBENCH_SUBPARTS_PER_GPU}" \
        > "${job_log}" 2>&1 &
    pids+=("$!")
  done
done

job_failed=0
for pid in "${pids[@]}"; do
  if ! wait "${pid}"; then
    job_failed=1
  fi
done

if [[ "${job_failed}" -ne 0 ]]; then
  echo "[05b_phononbench_stability] one or more phonon jobs failed; inspect ${JOB_LOG_DIR}" | tee -a "${PHONONBENCH_LOG_PATH}"
  exit 1
fi

python "${SCRIPT_DIR}/collect_phononbench_stability.py" \
  --input_dir "${PHONONBENCH_INPUT_CIF_DIR}" \
  --relaxed_dir "${PHONONBENCH_RELAXED_DIR}" \
  --all_output_csv "${PHONONBENCH_ALL_OUTPUT_CSV}" \
  --stable_output_csv "${PHONONBENCH_STABLE_OUTPUT_CSV}" \
  --stable_cif_dir "${PHONONBENCH_STABLE_CIF_DIR}" \
  --summary_json "${PHONONBENCH_SUMMARY_JSON}" 2>&1 | tee -a "${PHONONBENCH_LOG_PATH}"

conda deactivate
