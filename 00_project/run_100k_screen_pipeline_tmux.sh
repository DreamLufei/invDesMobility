#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/paths.sh"

SESSION_NAME="${SESSION_NAME:-invdes-100k-pipeline}"
GEN_RUN_ID="${GEN_RUN_ID:-20260417__generated_100000_structures__from_mobility2d_highquality280_ft_v1}"
GEN_CIF_DIR="${GEN_CIF_DIR:-${RUNS_ROOT}/${GEN_RUN_ID}/03_generate_structures/generated_cif}"
PIPELINE_RUN_ID="${PIPELINE_RUN_ID:-20260417__from_20260417_generated_100000_structures__dedup_generated_and_source_cif__orthorhombic__eform_lt_0p0eV_atom__phonon_stable_imag0p1__bg_gt_1p0eV__strict90__mobility_rank__top10}"
PHONONBENCH_GPU_LIST="${PHONONBENCH_GPU_LIST:-0,1,2,3}"
PHONONBENCH_SUBPARTS_PER_GPU="${PHONONBENCH_SUBPARTS_PER_GPU:-1}"
PHONONBENCH_DIM="${PHONONBENCH_DIM:-2 2 2}"
PHONONBENCH_IMAG_THRESHOLD="${PHONONBENCH_IMAG_THRESHOLD:-0.1}"
TOP_K="${TOP_K:-10}"

if [[ ! -d "${GEN_CIF_DIR}" ]]; then
  echo "[run_100k_screen_pipeline_tmux] missing generated CIF directory: ${GEN_CIF_DIR}" >&2
  exit 2
fi

if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
  echo "[run_100k_screen_pipeline_tmux] tmux session already exists: ${SESSION_NAME}" >&2
  echo "Attach with: tmux attach -t ${SESSION_NAME}" >&2
  exit 2
fi

PIPELINE_CMD="
cd '${INVDES_ROOT}' && \
source '${SCRIPT_DIR}/paths.sh' && \
INPUT_SOURCE_DIR='${GEN_CIF_DIR}' \
SOURCE_RUN_LABEL='${GEN_RUN_ID}' \
SOURCE_RUN_ID='${GEN_RUN_ID}' \
RUN_NAME='${PIPELINE_RUN_ID}' \
TARGET_CRYSTAL_SYSTEM='orthorhombic' \
DEDUP_REFERENCE_DIR='${SOURCE_CIF_REFERENCE_ROOT}' \
DEDUP_FORMATION_ENERGY_THRESHOLD='0.0' \
DEDUP_BANDGAP_THRESHOLD='1.0' \
PHONONBENCH_GPU_LIST='${PHONONBENCH_GPU_LIST}' \
PHONONBENCH_SUBPARTS_PER_GPU='${PHONONBENCH_SUBPARTS_PER_GPU}' \
PHONONBENCH_DIM='${PHONONBENCH_DIM}' \
PHONONBENCH_IMAG_THRESHOLD='${PHONONBENCH_IMAG_THRESHOLD}' \
TOP_K='${TOP_K}' \
bash '05_steps/08_orchestration/run_dedup_orthorhombic_semiconductor_pipeline.sh'
"

tmux new-session -d -s "${SESSION_NAME}" "bash -lc \"${PIPELINE_CMD}\""

echo "Started tmux session: ${SESSION_NAME}"
echo "Pipeline run id: ${PIPELINE_RUN_ID}"
echo "Generated CIF input: ${GEN_CIF_DIR}"
echo "Attach: tmux attach -t ${SESSION_NAME}"
echo "Progress: bash ${SCRIPT_DIR}/show_pipeline_progress.sh ${PIPELINE_RUN_ID}"

