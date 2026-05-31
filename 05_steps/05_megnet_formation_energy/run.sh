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
conda activate megnet-form

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_formation_energy}"
DEFAULT_MODEL_PATH="${MEGNET_MODEL_PATH}"
DEFAULT_MODEL_CONFIG_PATH="${MEGNET_MODEL_CONFIG_PATH}"
MODEL_PATH="${MEGNET_MODEL_PATH_OVERRIDE:-${DEFAULT_MODEL_PATH}}"
MODEL_CONFIG_PATH="${MEGNET_MODEL_CONFIG_PATH_OVERRIDE:-${DEFAULT_MODEL_CONFIG_PATH}}"
INPUT_CSV="${MEGNET_INPUT_CSV:-${RUNS_ROOT}/${RUN_ID}/02_alignn_bandgap_nonmetal/nonmetal_candidates.csv}"
INPUT_DIR="${MEGNET_INPUT_CIF_DIR:-${DEFAULT_GENERATION_CIF_DIR}}"
OUTPUT_CSV="${MEGNET_OUTPUT_CSV:-${RUNS_ROOT}/${RUN_ID}/03_megnet_formation_energy/formation_energy_predictions.csv}"
LOG_PATH="${MEGNET_LOG_PATH:-${LOGS_ROOT}/05_megnet_formation_energy/${RUN_ID}__formation.log}"

mkdir -p "$(dirname "${OUTPUT_CSV}")" "$(dirname "${LOG_PATH}")"

if [[ ! -f "${MODEL_PATH}" ]]; then
  echo "[07_run_formation_energy] missing MEGNet model file: ${MODEL_PATH}" | tee "${LOG_PATH}"
  exit 2
fi

if [[ ! -f "${MODEL_CONFIG_PATH}" ]]; then
  echo "[07_run_formation_energy] missing MEGNet config file: ${MODEL_CONFIG_PATH}" | tee -a "${LOG_PATH}"
  exit 2
fi

python "${MEGNET_PREDICT_SCRIPT}" \
  --model_path "${MODEL_PATH}" \
  --model_config_path "${MODEL_CONFIG_PATH}" \
  --cif_dir "${INPUT_DIR}" \
  --input_csv "${INPUT_CSV}" \
  --output_csv "${OUTPUT_CSV}" \
  --log_path "${LOG_PATH}" 2>&1 | tee -a "${LOG_PATH}"
