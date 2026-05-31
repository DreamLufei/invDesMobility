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
conda activate alignn-screen

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_bandgap_screen}"
DEFAULT_CONFIG_PATH="${ALIGNN_BANDGAP_CONFIG}"
DEFAULT_CHECKPOINT_PATH="${ALIGNN_BANDGAP_CKPT}"
CONFIG_PATH="${ALIGNN_BANDGAP_CONFIG_OVERRIDE:-${DEFAULT_CONFIG_PATH}}"
CHECKPOINT_PATH="${ALIGNN_BANDGAP_CHECKPOINT_OVERRIDE:-${DEFAULT_CHECKPOINT_PATH}}"
INPUT_CIF_DIR="${ALIGNN_CIF_INPUT_DIR:-${DEFAULT_GENERATION_CIF_DIR}}"
OUTPUT_CSV="${ALIGNN_BANDGAP_OUTPUT_CSV:-${RUNS_ROOT}/${RUN_ID}/02_alignn_bandgap_nonmetal/bandgap_predictions.csv}"
NONMETAL_CSV="${ALIGNN_NONMETAL_OUTPUT_CSV:-${RUNS_ROOT}/${RUN_ID}/02_alignn_bandgap_nonmetal/nonmetal_candidates.csv}"
LOG_PATH="${ALIGNN_BANDGAP_LOG_PATH:-${LOGS_ROOT}/04_alignn_bandgap_nonmetal/${RUN_ID}__bandgap.log}"

mkdir -p "$(dirname "${OUTPUT_CSV}")" "$(dirname "${LOG_PATH}")"

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "[06_run_bandgap_screen] missing ALIGNN config: ${CONFIG_PATH}" | tee "${LOG_PATH}"
  exit 2
fi

if [[ ! -f "${CHECKPOINT_PATH}" ]]; then
  echo "[06_run_bandgap_screen] missing ALIGNN checkpoint: ${CHECKPOINT_PATH}" | tee -a "${LOG_PATH}"
  exit 2
fi

if [[ ! -d "${INPUT_CIF_DIR}" ]]; then
  echo "[06_run_bandgap_screen] missing generated CIF directory: ${INPUT_CIF_DIR}" | tee -a "${LOG_PATH}"
  exit 2
fi

export ALIGNN_BANDGAP_CONFIG="${CONFIG_PATH}"
export ALIGNN_BANDGAP_CHECKPOINT="${CHECKPOINT_PATH}"
export ALIGNN_CIF_INPUT_DIR="${INPUT_CIF_DIR}"
export ALIGNN_BANDGAP_OUTPUT_CSV="${OUTPUT_CSV}"
export ALIGNN_NONMETAL_OUTPUT_CSV="${NONMETAL_CSV}"
export ALIGNN_BANDGAP_THRESHOLD="${CASE_ALIGNN_BANDGAP_THRESHOLD:-${ALIGNN_BANDGAP_THRESHOLD:-0.4}}"

python "${SCRIPT_DIR}/predict-ins-or-tmetal.py" 2>&1 | tee -a "${LOG_PATH}"
