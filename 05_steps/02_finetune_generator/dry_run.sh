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
CKPT_PATH="${CKPT_PATH:-${DIFFCSP_PRETRAINED_CKPT}}"
EXP_NAME="${EXP_NAME:-${DIFFCSP_EXPNAME}_dryrun}"
REPORT_PATH="${REPORT_PATH:-${LOGS_ROOT}/02_finetune_generator/${EXP_NAME}_ckpt_compat.json}"
FILTERED_CKPT_PATH="${FILTERED_CKPT_PATH:-${LOGS_ROOT}/02_finetune_generator/${EXP_NAME}_filtered.ckpt}"
LOG_PATH="${LOG_PATH:-${LOGS_ROOT}/02_finetune_generator/${EXP_NAME}.log}"
mkdir -p "$(dirname "${LOG_PATH}")"

set +e
python "${SCRIPT_DIR}/check_diffcsp_ckpt_compat.py" \
  --ckpt_path "${CKPT_PATH}" \
  --dataset_name "${DIFFCSP_DATASET_NAME}" \
  --expname "${EXP_NAME}" \
  --report_path "${REPORT_PATH}" \
  --filtered_ckpt_path "${FILTERED_CKPT_PATH}"
compat_status=$?
set -e

if [[ "${compat_status}" -ne 0 && "${compat_status}" -ne 2 ]]; then
  echo "[02_finetune_generator_dry_run] compatibility check failed with status ${compat_status}" | tee "${LOG_PATH}"
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
  echo "[02_finetune_generator_dry_run] using filtered warm-start checkpoint: ${FILTERED_CKPT_PATH}" | tee -a "${LOG_PATH}"
else
  echo "[02_finetune_generator_dry_run] using original warm-start checkpoint: ${CKPT_PATH}" | tee -a "${LOG_PATH}"
fi

cd "${DIFF_ROOT}"
python diffcsp/run.py \
  data="${DIFFCSP_DATASET_NAME}" \
  model=diffusion_w_type \
  expname="${EXP_NAME}" \
  logging.wandb.mode=offline \
  train.pl_trainer.fast_dev_run=True \
  +train.init_from_ckpt="${INIT_CKPT_PATH}" \
  +train.init_strict="${INIT_STRICT}" \
  optim.optimizer.lr=5e-5 2>&1 | tee "${LOG_PATH}"
