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

DIFF_ROOT="${DIFFCSP_ROOT}"
DATASET_NAME="${DATASET_NAME:-${DIFFCSP_DATASET_NAME}}"
CKPT_PATH="${CKPT_PATH:-${DIFFCSP_PRETRAINED_CKPT}}"
EXP_NAME="${EXP_NAME:-${DIFFCSP_EXPNAME}}"
REPORT_PATH="${REPORT_PATH:-${LOGS_ROOT}/02_finetune_generator/${EXP_NAME}_ckpt_compat.json}"
FILTERED_CKPT_PATH="${FILTERED_CKPT_PATH:-${LOGS_ROOT}/02_finetune_generator/${EXP_NAME}_filtered.ckpt}"
LOG_PATH="${LOG_PATH:-${LOGS_ROOT}/02_finetune_generator/${EXP_NAME}.log}"
FINETUNED_DIR="${FINETUNED_DIR:-${DIFFCSP_FINETUNED_DIR}}"
mkdir -p "$(dirname "${LOG_PATH}")" "$(dirname "${REPORT_PATH}")" "$(dirname "${FILTERED_CKPT_PATH}")" "${FINETUNED_DIR}"

set +e
python "${SCRIPT_DIR}/check_diffcsp_ckpt_compat.py" \
  --ckpt_path "${CKPT_PATH}" \
  --dataset_name "${DATASET_NAME}" \
  --expname "${EXP_NAME}" \
  --report_path "${REPORT_PATH}" \
  --filtered_ckpt_path "${FILTERED_CKPT_PATH}"
compat_status=$?
set -e

if [[ "${compat_status}" -ne 0 && "${compat_status}" -ne 2 ]]; then
  echo "[02_finetune_generator] compatibility check failed with status ${compat_status}" | tee "${LOG_PATH}"
  exit "${compat_status}"
fi

readarray -t CKPT_INFO < <(
REPORT_PATH="${REPORT_PATH}" python - <<'PY'
import json
import os
report_path = os.environ["REPORT_PATH"]
with open(report_path) as fh:
    report = json.load(fh)
print(report["compatible"])
PY
)

CKPT_COMPATIBLE="${CKPT_INFO[0]}"
INIT_CKPT_PATH="${CKPT_PATH}"
INIT_STRICT="true"

if [[ "${CKPT_COMPATIBLE}" != "True" ]]; then
  INIT_CKPT_PATH="${FILTERED_CKPT_PATH}"
  INIT_STRICT="false"
  echo "[02_finetune_generator] using filtered warm-start checkpoint: ${FILTERED_CKPT_PATH}" | tee -a "${LOG_PATH}"
else
  echo "[02_finetune_generator] using original warm-start checkpoint: ${CKPT_PATH}" | tee -a "${LOG_PATH}"
fi

cd "${DIFF_ROOT}"
python diffcsp/run.py \
  data="${DATASET_NAME}" \
  model=diffusion_w_type \
  expname="${EXP_NAME}" \
  logging.wandb.mode=offline \
  +train.init_from_ckpt="${INIT_CKPT_PATH}" \
  +train.init_strict="${INIT_STRICT}" \
  optim.optimizer.lr=5e-5 2>&1 | tee "${LOG_PATH}"

LATEST_RUN_DIR="$(
  find "${HYDRA_JOBS}/singlerun" -type d -name "${EXP_NAME}" | sort | tail -n 1
)"
if [[ -n "${LATEST_RUN_DIR}" && -d "${LATEST_RUN_DIR}" ]]; then
  cp -f "${LATEST_RUN_DIR}/epoch="* "${FINETUNED_DIR}/" 2>/dev/null || true
  cp -f "${LATEST_RUN_DIR}/hparams.yaml" "${FINETUNED_DIR}/hparams.yaml"
  cp -f "${LATEST_RUN_DIR}/lattice_scaler.pt" "${FINETUNED_DIR}/lattice_scaler.pt"
  cp -f "${LATEST_RUN_DIR}/prop_scaler.pt" "${FINETUNED_DIR}/prop_scaler.pt"
  cp -f "${LATEST_RUN_DIR}/run.log" "${FINETUNED_DIR}/run.log"
  if [[ -f "${LATEST_RUN_DIR}/epoch=714-step=28599.ckpt" ]]; then
    cp -f "${LATEST_RUN_DIR}/epoch=714-step=28599.ckpt" "${FINETUNED_DIR}/best.ckpt"
  else
    BEST_CKPT="$(find "${LATEST_RUN_DIR}" -maxdepth 1 -name 'epoch=*.ckpt' | sort | tail -n 1)"
    if [[ -n "${BEST_CKPT}" ]]; then
      cp -f "${BEST_CKPT}" "${FINETUNED_DIR}/best.ckpt"
    fi
  fi
fi
