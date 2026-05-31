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

RUN_ID="${RUN_ID:-$(date +%Y%m%d)_stage1_run}"
RUN_ROOT="${RUN_ROOT:-${RUNS_ROOT}/${RUN_ID}}"
RUN_LOG_DIR="${LOGS_BY_RUN_ROOT}/${RUN_ID}"
PT_OUTPUT_DIR="${RUN_ROOT}/03_generate_structures/generated_pt"
CIF_OUTPUT_DIR="${RUN_ROOT}/03_generate_structures/generated_cif"
PT_TO_CIF_LOG="${RUN_LOG_DIR}/04_pt_to_cif_bad_samples.log"
RUN_FINETUNE="${RUN_FINETUNE:-1}"

mkdir -p "${RUN_ROOT}/01_build_dataset" "${RUN_ROOT}/02_finetune_generator" "${PT_OUTPUT_DIR}" "${CIF_OUTPUT_DIR}" "${RUN_LOG_DIR}"

bash "${STEP01_DIR}/run.sh"
ln -sfn "${DIFFCSP_DATASET_DIR}" "${RUN_ROOT}/01_build_dataset/mobility2d_highquality280"

if [[ "${RUN_FINETUNE}" == "1" ]]; then
  bash "${STEP02_DIR}/run.sh"
fi

export RUN_ID
export RUN_ROOT
export OUTPUT_DIR="${PT_OUTPUT_DIR}"
export LOG_PATH="${RUN_LOG_DIR}/03_generate_structures.log"
bash "${STEP03_DIR}/run.sh"

CONDA_BASE="${CONDA_BASE:-$(conda info --base)}"
source "${CONDA_BASE}/etc/profile.d/conda.sh"
conda activate diffcsp-gen
source "${PROJECT_ROOT}/diffcsp_runtime.sh"
python "${STEP03_DIR}/pt_to_cif.py" \
  --input_dir "${PT_OUTPUT_DIR}" \
  --output_dir "${CIF_OUTPUT_DIR}" \
  --log_path "${PT_TO_CIF_LOG}"

RUN_ROOT="${RUN_ROOT}" RUN_ID="${RUN_ID}" RUN_FINETUNE="${RUN_FINETUNE}" PT_OUTPUT_DIR="${PT_OUTPUT_DIR}" CIF_OUTPUT_DIR="${CIF_OUTPUT_DIR}" python - <<'PY'
import json
import os
from pathlib import Path

run_root = Path(os.environ["RUN_ROOT"])
manifest = {
    "run_id": os.environ["RUN_ID"],
    "run_finetune": os.environ["RUN_FINETUNE"] == "1",
    "generated_pt_dir": os.environ["PT_OUTPUT_DIR"],
    "generated_cif_dir": os.environ["CIF_OUTPUT_DIR"],
    "run_log_dir": str(run_root.parent.parent / "07_logs" / "09_runs_by_name" / os.environ["RUN_ID"]),
}
(run_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
PY

echo "[run_stage1] completed: ${RUN_ROOT}"
