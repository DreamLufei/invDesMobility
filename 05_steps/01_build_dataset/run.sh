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

INV_ROOT="${INV_DES_FLOW_ROOT}"
CIF_DIR="${CIF_DIR:-${SOURCE_CIF_DIR}}"
DATASET_NAME="${DATASET_NAME:-${DIFFCSP_DATASET_NAME}}"
OUT_DIR="${DIFFCSP_DATASET_DIR}"
LOG_PATH="${LOG_PATH:-${LOGS_ROOT}/01_build_dataset/01_build_dataset.log}"

mkdir -p "$(dirname "${LOG_PATH}")"

if [[ -f "${OUT_DIR}/train.csv" && -f "${OUT_DIR}/val.csv" && -f "${OUT_DIR}/test.csv" ]]; then
  echo "[01_build_dataset] dataset already exists at ${OUT_DIR}" | tee "${LOG_PATH}"
  exit 0
fi

cd "${INV_ROOT}"
python cif2dataset.py \
  --cif_dir "${CIF_DIR}" \
  --dataset_name "${DATASET_NAME}" 2>&1 | tee "${LOG_PATH}"

echo "[01_build_dataset] dataset written to ${OUT_DIR}" | tee -a "${LOG_PATH}"
