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

format_threshold_token() {
  local value="$1"
  value="${value//./p}"
  if [[ "${value}" == -* ]]; then
    value="neg${value#-}"
  fi
  echo "${value}"
}

INPUT_SOURCE_DIR="${INPUT_SOURCE_DIR:-${DEFAULT_GENERATION_CIF_DIR}}"
SOURCE_RUN_NAME_DEFAULT="$(basename "$(dirname "$(dirname "${INPUT_SOURCE_DIR}")")")"
SOURCE_RUN_LABEL="${SOURCE_RUN_LABEL:-${SOURCE_RUN_NAME_DEFAULT}}"
SOURCE_RUN_ID="${SOURCE_RUN_ID:-${SOURCE_RUN_NAME_DEFAULT}}"
TARGET_CRYSTAL_SYSTEM="${TARGET_CRYSTAL_SYSTEM:-orthorhombic}"
BANDGAP_THRESHOLD="${CASE_BANDGAP_THRESHOLD:-${ORTHO_BANDGAP_THRESHOLD:-1.0}}"
FORMATION_ENERGY_THRESHOLD="${CASE_FORMATION_THRESHOLD:-${ORTHO_FORMATION_ENERGY_THRESHOLD:--0.5}}"
TOP_K="${TOP_K:-10}"
SYMPREC="${SYMPREC:-0.1}"
ANGLE_TOLERANCE="${ANGLE_TOLERANCE:-5.0}"

BG_TOKEN="$(format_threshold_token "${BANDGAP_THRESHOLD}")"
EFORM_TOKEN="$(format_threshold_token "${FORMATION_ENERGY_THRESHOLD}")"
RUN_NAME="${RUN_NAME:-$(date +%Y%m%d)__from_${SOURCE_RUN_LABEL}__${TARGET_CRYSTAL_SYSTEM}__bg_gt_${BG_TOKEN}eV__eform_lt_${EFORM_TOKEN}eV_atom__mobility_rank}"
RUN_ROOT="${RUN_ROOT:-${RUNS_ROOT}/${RUN_NAME}}"
RUN_LOG_DIR="${LOGS_BY_RUN_ROOT}/${RUN_NAME}"
ORCH_LOG_PATH="${RUN_LOG_DIR}/00_orchestration.log"

RUN_STEP01_DIR="${RUN_ROOT}/01_input_generated_cif"
RUN_STEP02_DIR="${RUN_ROOT}/02_orthorhombic_filter"
RUN_STEP03_DIR="${RUN_ROOT}/03_alignn_bandgap_screen"
RUN_STEP04_DIR="${RUN_ROOT}/04_megnet_formation_energy"
RUN_STEP05_DIR="${RUN_ROOT}/05_candidates_after_thresholds"
RUN_STEP06_DIR="${RUN_ROOT}/06_alignn_mobility_rank"
RUN_STEP07_DIR="${RUN_ROOT}/07_top10_cif"

if [[ -e "${RUN_ROOT}" || -L "${RUN_ROOT}" ]]; then
  echo "[run_orthorhombic_semiconductor_pipeline] target run already exists: ${RUN_ROOT}" >&2
  exit 2
fi

mkdir -p \
  "${RUN_ROOT}" \
  "${RUN_LOG_DIR}" \
  "${RUN_STEP02_DIR}" \
  "${RUN_STEP03_DIR}" \
  "${RUN_STEP04_DIR}" \
  "${RUN_STEP05_DIR}" \
  "${RUN_STEP06_DIR}" \
  "${RUN_STEP07_DIR}"
exec > >(tee -a "${ORCH_LOG_PATH}") 2>&1

if [[ ! -d "${INPUT_SOURCE_DIR}" ]]; then
  echo "[run_orthorhombic_semiconductor_pipeline] missing input CIF dir: ${INPUT_SOURCE_DIR}" >&2
  exit 2
fi

ln -sfn "${INPUT_SOURCE_DIR}" "${RUN_STEP01_DIR}"

echo "[run_orthorhombic_semiconductor_pipeline] step 02: crystal-system filter"
CONDA_BASE="${CONDA_BASE:-$(conda info --base)}"
# shellcheck disable=SC1091
source "${CONDA_BASE}/etc/profile.d/conda.sh"
conda activate diffcsp-gen
python "${SCRIPT_DIR}/filter_cifs_by_crystal_system.py" \
  --input_dir "${RUN_STEP01_DIR}" \
  --all_output_csv "${RUN_STEP02_DIR}/crystal_system_all.csv" \
  --selected_output_csv "${RUN_STEP02_DIR}/orthorhombic_candidates.csv" \
  --failures_output_csv "${RUN_STEP02_DIR}/parse_failures.csv" \
  --selected_cif_dir "${RUN_STEP02_DIR}/orthorhombic_cif" \
  --summary_json "${RUN_STEP02_DIR}/orthorhombic_summary.json" \
  --target_crystal_system "${TARGET_CRYSTAL_SYSTEM}" \
  --symprec "${SYMPREC}" \
  --angle_tolerance "${ANGLE_TOLERANCE}" | tee "${RUN_LOG_DIR}/02_orthorhombic_filter.log"
conda deactivate

echo "[run_orthorhombic_semiconductor_pipeline] step 03: bandgap screening"
RUN_ID="${RUN_NAME}" \
ALIGNN_CIF_INPUT_DIR="${RUN_STEP02_DIR}/orthorhombic_cif" \
CASE_ALIGNN_BANDGAP_THRESHOLD="${BANDGAP_THRESHOLD}" \
ALIGNN_BANDGAP_OUTPUT_CSV="${RUN_STEP03_DIR}/bandgap_predictions.csv" \
ALIGNN_NONMETAL_OUTPUT_CSV="${RUN_STEP03_DIR}/nonmetal_candidates.csv" \
ALIGNN_BANDGAP_LOG_PATH="${RUN_LOG_DIR}/03_alignn_bandgap_screen.log" \
bash "${STEP04_DIR}/run.sh"

echo "[run_orthorhombic_semiconductor_pipeline] step 04: formation-energy prediction"
RUN_ID="${RUN_NAME}" \
MEGNET_INPUT_CSV="${RUN_STEP03_DIR}/nonmetal_candidates.csv" \
MEGNET_INPUT_CIF_DIR="${RUN_STEP02_DIR}/orthorhombic_cif" \
MEGNET_OUTPUT_CSV="${RUN_STEP04_DIR}/formation_energy_predictions.csv" \
MEGNET_LOG_PATH="${RUN_LOG_DIR}/04_megnet_formation_energy.log" \
bash "${STEP05_DIR}/run.sh"

echo "[run_orthorhombic_semiconductor_pipeline] step 05: threshold filtering"
python "${SCRIPT_DIR}/build_threshold_case.py" \
  --run_id "${RUN_NAME}" \
  --source_input_dir "${RUN_STEP02_DIR}/orthorhombic_cif" \
  --bandgap_csv "${RUN_STEP03_DIR}/nonmetal_candidates.csv" \
  --formation_csv "${RUN_STEP04_DIR}/formation_energy_predictions.csv" \
  --merged_output_csv "${RUN_STEP04_DIR}/formation_energy_merged.csv" \
  --missing_output_csv "${RUN_STEP04_DIR}/missing_formation_predictions.csv" \
  --candidates_output_csv "${RUN_STEP05_DIR}/candidates.csv" \
  --summary_json "${RUN_STEP05_DIR}/threshold_summary.json" \
  --bandgap_threshold "${BANDGAP_THRESHOLD}" \
  --formation_threshold "${FORMATION_ENERGY_THRESHOLD}" | tee "${RUN_LOG_DIR}/05_candidates_after_thresholds.log"

echo "[run_orthorhombic_semiconductor_pipeline] step 06: mobility ranking"
source "${CONDA_BASE}/etc/profile.d/conda.sh"
conda activate alignn-screen
python "${STEP06_DIR}/predict_alignn_mobility.py" \
  --input_csv "${RUN_STEP05_DIR}/candidates.csv" \
  --output_csv "${RUN_STEP06_DIR}/mobility_predictions.csv" \
  --ranked_output_csv "${RUN_STEP06_DIR}/mobility_ranked_candidates.csv" \
  --log_path "${RUN_LOG_DIR}/06_alignn_mobility_rank.log"
conda deactivate

echo "[run_orthorhombic_semiconductor_pipeline] step 07: top${TOP_K} export"
RANKED_CSV="${RUN_STEP06_DIR}/mobility_ranked_candidates.csv" \
OUTPUT_DIR="${RUN_STEP07_DIR}" \
SUMMARY_CSV="${RUN_STEP07_DIR}/top10_candidates.csv" \
TOP_K="${TOP_K}" \
LOG_PATH="${RUN_LOG_DIR}/07_top10_cif.log" \
bash "${STEP07_DIR}/run.sh"

echo "[run_orthorhombic_semiconductor_pipeline] writing manifest"
python - "${RUN_NAME}" "${SOURCE_RUN_ID}" "${SOURCE_RUN_LABEL}" "${INPUT_SOURCE_DIR}" "${TARGET_CRYSTAL_SYSTEM}" "${BANDGAP_THRESHOLD}" "${FORMATION_ENERGY_THRESHOLD}" "${SYMPREC}" "${ANGLE_TOLERANCE}" "${TOP_K}" "${RUN_ROOT}" "${RUN_LOG_DIR}" "${RUN_STEP02_DIR}/orthorhombic_summary.json" "${RUN_STEP05_DIR}/threshold_summary.json" "${ALIGNN_MOBILITY_MODEL_CKPT}" <<'PY'
import csv
import json
import sys
from pathlib import Path


def read_csv_rows(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


run_id = sys.argv[1]
source_run_id = sys.argv[2]
source_run_label = sys.argv[3]
source_input_dir = sys.argv[4]
target_crystal_system = sys.argv[5]
bandgap_threshold = float(sys.argv[6])
formation_threshold = float(sys.argv[7])
symprec = float(sys.argv[8])
angle_tolerance = float(sys.argv[9])
top_k = int(sys.argv[10])
run_root = Path(sys.argv[11])
run_log_dir = sys.argv[12]
orth_summary = json.loads(Path(sys.argv[13]).read_text())
threshold_summary = json.loads(Path(sys.argv[14]).read_text())
mobility_model_path = sys.argv[15]

bandgap_prediction_rows = read_csv_rows(run_root / "03_alignn_bandgap_screen" / "bandgap_predictions.csv")
bandgap_pass_rows = read_csv_rows(run_root / "03_alignn_bandgap_screen" / "nonmetal_candidates.csv")
formation_rows = read_csv_rows(run_root / "04_megnet_formation_energy" / "formation_energy_predictions.csv")
merged_rows = read_csv_rows(run_root / "04_megnet_formation_energy" / "formation_energy_merged.csv")
missing_rows = read_csv_rows(run_root / "04_megnet_formation_energy" / "missing_formation_predictions.csv")
candidates_rows = read_csv_rows(run_root / "05_candidates_after_thresholds" / "candidates.csv")
ranked_rows = read_csv_rows(run_root / "06_alignn_mobility_rank" / "mobility_ranked_candidates.csv")
top_rows = read_csv_rows(run_root / "07_top10_cif" / "top10_candidates.csv")

manifest = {
    "run_id": run_id,
    "source_generation_run_id": source_run_id,
    "source_generation_run_label": source_run_label,
    "source_input_dir": source_input_dir,
    "target_crystal_system": target_crystal_system,
    "symprec": symprec,
    "angle_tolerance": angle_tolerance,
    "bandgap_threshold_ev": bandgap_threshold,
    "formation_threshold_ev_per_atom": formation_threshold,
    "mobility_model_path": mobility_model_path,
    "top_k": top_k,
    "run_log_dir": run_log_dir,
    "counts": {
        "source_input_cif_total": orth_summary["counts"]["input_cif_total"],
        "orthorhombic_selected_count": orth_summary["counts"]["selected_cif_total"],
        "orthorhombic_parse_failures": orth_summary["counts"]["parse_failures"],
        "bandgap_predictions_total": len(bandgap_prediction_rows),
        "bandgap_pass_count": len(bandgap_pass_rows),
        "formation_predictions_total": len(formation_rows),
        "matched_formation_rows": len(merged_rows),
        "missing_formation_rows": len(missing_rows),
        "selected_candidates": len(candidates_rows),
        "mobility_ranked_candidates": len(ranked_rows),
        "exported_topk": len(top_rows),
    },
    "paths": {
        "orthorhombic_all_csv": str(run_root / "02_orthorhombic_filter" / "crystal_system_all.csv"),
        "orthorhombic_candidates_csv": str(run_root / "02_orthorhombic_filter" / "orthorhombic_candidates.csv"),
        "orthorhombic_failures_csv": str(run_root / "02_orthorhombic_filter" / "parse_failures.csv"),
        "orthorhombic_cif_dir": str(run_root / "02_orthorhombic_filter" / "orthorhombic_cif"),
        "bandgap_predictions_csv": str(run_root / "03_alignn_bandgap_screen" / "bandgap_predictions.csv"),
        "formation_predictions_csv": str(run_root / "04_megnet_formation_energy" / "formation_energy_predictions.csv"),
        "formation_merged_csv": str(run_root / "04_megnet_formation_energy" / "formation_energy_merged.csv"),
        "missing_formation_csv": str(run_root / "04_megnet_formation_energy" / "missing_formation_predictions.csv"),
        "candidates_csv": str(run_root / "05_candidates_after_thresholds" / "candidates.csv"),
        "mobility_ranked_csv": str(run_root / "06_alignn_mobility_rank" / "mobility_ranked_candidates.csv"),
        "topk_summary_csv": str(run_root / "07_top10_cif" / "top10_candidates.csv"),
    },
}
(run_root / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
print(json.dumps(manifest, indent=2, ensure_ascii=False))
PY

echo "[run_orthorhombic_semiconductor_pipeline] completed: ${RUN_ROOT}"
