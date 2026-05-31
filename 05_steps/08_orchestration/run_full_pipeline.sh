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

STAGE1_RUN_ID="${STAGE1_RUN_ID:-$(date +%Y%m%d)__stage1__build_finetune_generate_structures}"
PIPELINE_RUN_ID="${PIPELINE_RUN_ID:-}"
RUN_FINETUNE="${RUN_FINETUNE:-0}"

RUN_ID="${STAGE1_RUN_ID}" RUN_FINETUNE="${RUN_FINETUNE}" bash "${SCRIPT_DIR}/run_stage1.sh"

if [[ -n "${PIPELINE_RUN_ID}" ]]; then
  INPUT_SOURCE_DIR="${RUNS_ROOT}/${STAGE1_RUN_ID}/03_generate_structures/generated_cif" \
  RUN_NAME="${PIPELINE_RUN_ID}" \
  bash "${SCRIPT_DIR}/run_semiconductor_pipeline.sh"
else
  INPUT_SOURCE_DIR="${RUNS_ROOT}/${STAGE1_RUN_ID}/03_generate_structures/generated_cif" \
  SOURCE_RUN_LABEL="${STAGE1_RUN_ID}" \
  bash "${SCRIPT_DIR}/run_semiconductor_pipeline.sh"
fi
