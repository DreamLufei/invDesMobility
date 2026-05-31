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

RUN_NAME="${RUN_NAME:-20260409__from_20260408_generated_1000_structures__orthorhombic__bg_gt_1p0eV__eform_lt_neg0p5eV_atom__mobility_rank}"
RUN_ROOT="${RUNS_ROOT}/${RUN_NAME}"
RUN_LOG_DIR="${LOGS_BY_RUN_ROOT}/${RUN_NAME}"
TARGET_CRYSTAL_SYSTEM="${TARGET_CRYSTAL_SYSTEM:-orthorhombic}"
MAX_ANGLE_DEVIATION_DEG="${MAX_ANGLE_DEVIATION_DEG:-0.6}"
SYMPREC="${SYMPREC:-0.1}"
ANGLE_TOLERANCE="${ANGLE_TOLERANCE:-5.0}"

if [[ ! -d "${RUN_ROOT}" ]]; then
  echo "[run_snap_to_strict90] missing run dir: ${RUN_ROOT}" >&2
  exit 2
fi

mkdir -p "${RUN_LOG_DIR}"

CONDA_BASE="${CONDA_BASE:-$(conda info --base)}"
# shellcheck disable=SC1091
source "${CONDA_BASE}/etc/profile.d/conda.sh"
conda activate diffcsp-gen

python "${SCRIPT_DIR}/snap_near_orthorhombic_to_strict90.py" \
  --input_dir "${RUN_ROOT}/02_orthorhombic_filter/orthorhombic_cif" \
  --output_dir "${RUN_ROOT}/02_orthorhombic_filter/orthorhombic_cif_strict90" \
  --summary_csv "${RUN_ROOT}/02_orthorhombic_filter/orthorhombic_cif_strict90_summary.csv" \
  --summary_json "${RUN_ROOT}/02_orthorhombic_filter/orthorhombic_cif_strict90_summary.json" \
  --target_crystal_system "${TARGET_CRYSTAL_SYSTEM}" \
  --max_angle_deviation_deg "${MAX_ANGLE_DEVIATION_DEG}" \
  --symprec "${SYMPREC}" \
  --angle_tolerance "${ANGLE_TOLERANCE}" \
  | tee "${RUN_LOG_DIR}/08_snap_to_strict90__02_orthorhombic_filter.log"

python "${SCRIPT_DIR}/snap_near_orthorhombic_to_strict90.py" \
  --input_dir "${RUN_ROOT}/07_top10_cif" \
  --output_dir "${RUN_ROOT}/07_top10_cif/strict90_cif" \
  --summary_csv "${RUN_ROOT}/07_top10_cif/strict90_summary.csv" \
  --summary_json "${RUN_ROOT}/07_top10_cif/strict90_summary.json" \
  --target_crystal_system "${TARGET_CRYSTAL_SYSTEM}" \
  --max_angle_deviation_deg "${MAX_ANGLE_DEVIATION_DEG}" \
  --symprec "${SYMPREC}" \
  --angle_tolerance "${ANGLE_TOLERANCE}" \
  | tee "${RUN_LOG_DIR}/09_snap_to_strict90__07_top10_cif.log"

conda deactivate

