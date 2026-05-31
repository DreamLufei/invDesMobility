#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT_DIR}/00_project/paths.sh"

CONDA_BASE="${CONDA_BASE:-$(conda info --base)}"
source "${CONDA_BASE}/etc/profile.d/conda.sh"
conda activate alignn-screen

ALIGNN_ROOT="${ALIGNN_CODE_ROOT}"
export PYTHONPATH="${ALIGNN_ROOT}:${PYTHONPATH:-}"
DATA_SCRIPT="${SCRIPT_DIR}/prepare_alignn_mobility_data.py"
PATCH_DGL_SCRIPT="${SCRIPT_DIR}/patch_dgl_graphbolt.py"
DATA_DIR="${ALIGNN_MOBILITY_DATA_DIR}"
CONFIG_PATH="${SCRIPT_DIR}/configs/mobility_reg_v1.json"
OUTPUT_DIR="${MODELS_ROOT}/04_alignn_mobility/mobility_reg_v1"
LOG_PATH="${LOGS_ROOT}/06_alignn_mobility_rank/09_train_alignn_mobility_reg.log"
GPU_ID="${GPU_ID:-0}"
RESTART_MODEL_PATH="${ALIGNN_MOBILITY_RESTART_MODEL_PATH:-}"
EFFECTIVE_RESTART_MODEL_PATH="${RESTART_MODEL_PATH}"

mkdir -p "$(dirname "${LOG_PATH}")" "${OUTPUT_DIR}"

python "${DATA_SCRIPT}" | tee "${LOGS_ROOT}/06_alignn_mobility_rank/08_prepare_alignn_mobility_data.log"
python "${PATCH_DGL_SCRIPT}" | tee "${LOGS_ROOT}/06_alignn_mobility_rank/08b_patch_dgl_graphbolt.log"

cd "${ALIGNN_ROOT}"
export DGLBACKEND=pytorch
export DGL_SKIP_GRAPHBOLT=1
if [[ -n "${EFFECTIVE_RESTART_MODEL_PATH}" && -f "${EFFECTIVE_RESTART_MODEL_PATH}" ]]; then
  restart_basename="$(basename "${EFFECTIVE_RESTART_MODEL_PATH}")"
  restart_dir="$(dirname "${EFFECTIVE_RESTART_MODEL_PATH}")"
  if [[ "${restart_basename}" == "best_model.pt" && -f "${restart_dir}/current_model.pt" ]]; then
    EFFECTIVE_RESTART_MODEL_PATH="${restart_dir}/current_model.pt"
  fi
fi
TRAIN_CMD=(
  python alignn/train_alignn.py
  --root_dir "${DATA_DIR}"
  --config_name "${CONFIG_PATH}"
  --file_format cif
  --output_dir "${OUTPUT_DIR}"
)
if [[ -n "${EFFECTIVE_RESTART_MODEL_PATH}" ]]; then
  TRAIN_CMD+=(--restart_model_path "${EFFECTIVE_RESTART_MODEL_PATH}")
fi

CUDA_VISIBLE_DEVICES="${GPU_ID}" "${TRAIN_CMD[@]}" 2>&1 | tee "${LOG_PATH}"
