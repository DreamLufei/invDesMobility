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

RUN_ID="${RUN_ID:?RUN_ID is required}"
SOURCE_GENERATION_RUN_ID="${SOURCE_GENERATION_RUN_ID:-${DEFAULT_GENERATION_RUN_ID}}"
SOURCE_GENERATION_DIR="${RUNS_ROOT}/${SOURCE_GENERATION_RUN_ID}"
INPUT_CIF_DIR="${INPUT_CIF_DIR:-${SOURCE_GENERATION_DIR}/03_generate_structures/generated_cif}"
BANDGAP_THRESHOLD="${CASE_BANDGAP_THRESHOLD:-${BANDGAP_THRESHOLD:-}}"
FORMATION_THRESHOLD="${CASE_FORMATION_THRESHOLD:-${FORMATION_THRESHOLD:-}}"
TOP_K="${TOP_K:-10}"
RUN_DIR="${RUNS_ROOT}/${RUN_ID}"
RUN_LOG_DIR="${LOGS_BY_RUN_ROOT}/${RUN_ID}"
ORCH_LOG_PATH="${RUN_LOG_DIR}/00_orchestration.log"
THRESHOLD_SUMMARY_JSON="${RUN_DIR}/04_candidates_after_thresholds/threshold_summary.json"

if [[ -z "${BANDGAP_THRESHOLD}" ]]; then
  echo "[run_threshold_case] missing bandgap threshold"
  exit 2
fi

if [[ -z "${FORMATION_THRESHOLD}" ]]; then
  echo "[run_threshold_case] missing formation threshold"
  exit 2
fi

if [[ -e "${RUN_DIR}" || -L "${RUN_DIR}" ]]; then
  echo "[run_threshold_case] target run dir already exists: ${RUN_DIR}"
  exit 2
fi

mkdir -p "${RUN_DIR}" "${RUN_LOG_DIR}"
exec > >(tee -a "${ORCH_LOG_PATH}") 2>&1

echo "[run_threshold_case] RUN_ID=${RUN_ID}"
echo "[run_threshold_case] SOURCE_GENERATION_RUN_ID=${SOURCE_GENERATION_RUN_ID}"
echo "[run_threshold_case] BANDGAP_THRESHOLD=${BANDGAP_THRESHOLD}"
echo "[run_threshold_case] FORMATION_THRESHOLD=${FORMATION_THRESHOLD}"

if [[ ! -d "${INPUT_CIF_DIR}" ]]; then
  echo "[run_threshold_case] missing input CIF dir: ${INPUT_CIF_DIR}"
  exit 2
fi

mkdir -p \
  "${RUN_DIR}/02_alignn_bandgap_screen" \
  "${RUN_DIR}/03_megnet_formation_energy" \
  "${RUN_DIR}/04_candidates_after_thresholds" \
  "${RUN_DIR}/05_alignn_mobility_rank" \
  "${RUN_DIR}/06_top10_cif"

ln -sfn "${INPUT_CIF_DIR}" "${RUN_DIR}/01_input_generated_cif"

echo "[run_threshold_case] step 02: bandgap screening"
RUN_ID="${RUN_ID}" \
ALIGNN_CIF_INPUT_DIR="${INPUT_CIF_DIR}" \
CASE_ALIGNN_BANDGAP_THRESHOLD="${BANDGAP_THRESHOLD}" \
ALIGNN_BANDGAP_OUTPUT_CSV="${RUN_DIR}/02_alignn_bandgap_screen/bandgap_predictions.csv" \
ALIGNN_NONMETAL_OUTPUT_CSV="${RUN_DIR}/02_alignn_bandgap_screen/nonmetal_candidates.csv" \
ALIGNN_BANDGAP_LOG_PATH="${RUN_LOG_DIR}/02_alignn_bandgap_screen.log" \
bash "${STEP04_DIR}/run.sh"

echo "[run_threshold_case] step 03: full formation-energy prediction"
RUN_ID="${RUN_ID}" \
MEGNET_INPUT_CIF_DIR="${INPUT_CIF_DIR}" \
MEGNET_INPUT_CSV="${RUN_DIR}/03_megnet_formation_energy/_scan_all_generated_cifs.csv" \
MEGNET_OUTPUT_CSV="${RUN_DIR}/03_megnet_formation_energy/formation_energy_predictions.csv" \
MEGNET_LOG_PATH="${RUN_LOG_DIR}/03_megnet_formation_energy.log" \
bash "${STEP05_DIR}/run.sh"

echo "[run_threshold_case] step 04: threshold filtering"
python "${SCRIPT_DIR}/build_threshold_case.py" \
  --run_id "${RUN_ID}" \
  --source_input_dir "${INPUT_CIF_DIR}" \
  --bandgap_csv "${RUN_DIR}/02_alignn_bandgap_screen/bandgap_predictions.csv" \
  --formation_csv "${RUN_DIR}/03_megnet_formation_energy/formation_energy_predictions.csv" \
  --merged_output_csv "${RUN_DIR}/03_megnet_formation_energy/formation_energy_merged.csv" \
  --missing_output_csv "${RUN_DIR}/03_megnet_formation_energy/missing_formation_predictions.csv" \
  --candidates_output_csv "${RUN_DIR}/04_candidates_after_thresholds/candidates.csv" \
  --summary_json "${THRESHOLD_SUMMARY_JSON}" \
  --bandgap_threshold "${BANDGAP_THRESHOLD}" \
  --formation_threshold "${FORMATION_THRESHOLD}" | tee "${RUN_LOG_DIR}/04_candidates_after_thresholds.log"

echo "[run_threshold_case] step 05: mobility ranking"
CONDA_BASE="${CONDA_BASE:-$(conda info --base)}"
# shellcheck disable=SC1091
source "${CONDA_BASE}/etc/profile.d/conda.sh"
conda activate alignn-screen
python "${STEP06_DIR}/predict_alignn_mobility.py" \
  --input_csv "${RUN_DIR}/04_candidates_after_thresholds/candidates.csv" \
  --output_csv "${RUN_DIR}/05_alignn_mobility_rank/mobility_predictions.csv" \
  --ranked_output_csv "${RUN_DIR}/05_alignn_mobility_rank/mobility_ranked_candidates.csv" \
  --log_path "${RUN_LOG_DIR}/05_alignn_mobility_rank.log"
conda deactivate

echo "[run_threshold_case] step 06: top${TOP_K} export"
RANKED_CSV="${RUN_DIR}/05_alignn_mobility_rank/mobility_ranked_candidates.csv" \
OUTPUT_DIR="${RUN_DIR}/06_top10_cif" \
SUMMARY_CSV="${RUN_DIR}/06_top10_cif/top10_candidates.csv" \
TOP_K="${TOP_K}" \
LOG_PATH="${RUN_LOG_DIR}/06_top10_cif.log" \
bash "${STEP07_DIR}/run.sh"

echo "[run_threshold_case] writing manifest"
python - "${RUN_ID}" "${SOURCE_GENERATION_RUN_ID}" "${INPUT_CIF_DIR}" "${BANDGAP_THRESHOLD}" "${FORMATION_THRESHOLD}" "${ALIGNN_MOBILITY_MODEL_CKPT}" "${TOP_K}" "${RUN_DIR}" "${THRESHOLD_SUMMARY_JSON}" <<'PY'
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
source_generation_run_id = sys.argv[2]
source_input_dir = sys.argv[3]
bandgap_threshold = float(sys.argv[4])
formation_threshold = float(sys.argv[5])
mobility_model_path = sys.argv[6]
top_k = int(sys.argv[7])
run_dir = Path(sys.argv[8])
threshold_summary_json = Path(sys.argv[9])

threshold_summary = json.loads(threshold_summary_json.read_text())
ranked_rows = read_csv_rows(run_dir / "05_alignn_mobility_rank" / "mobility_ranked_candidates.csv")
top_rows = read_csv_rows(run_dir / "06_top10_cif" / "top10_candidates.csv")

manifest = {
    "run_id": run_id,
    "source_generation_run_id": source_generation_run_id,
    "source_input_dir": source_input_dir,
    "bandgap_threshold_ev": bandgap_threshold,
    "formation_threshold_ev_per_atom": formation_threshold,
    "mobility_model_path": mobility_model_path,
    "top_k": top_k,
    "counts": {
        "input_cif_total": threshold_summary["counts"]["input_cif_total"],
        "bandgap_predictions_total": threshold_summary["counts"]["bandgap_predictions_total"],
        "bandgap_pass_count": threshold_summary["counts"]["bandgap_pass_count"],
        "formation_predictions_total": threshold_summary["counts"]["formation_predictions_total"],
        "matched_formation_rows": threshold_summary["counts"]["matched_formation_rows"],
        "missing_formation_rows": threshold_summary["counts"]["missing_formation_rows"],
        "selected_candidates": threshold_summary["counts"]["selected_candidates"],
        "mobility_ranked_candidates": len(ranked_rows),
        "exported_topk": len(top_rows),
    },
    "paths": {
        "bandgap_predictions_csv": str(run_dir / "02_alignn_bandgap_screen" / "bandgap_predictions.csv"),
        "formation_predictions_csv": str(run_dir / "03_megnet_formation_energy" / "formation_energy_predictions.csv"),
        "formation_merged_csv": str(run_dir / "03_megnet_formation_energy" / "formation_energy_merged.csv"),
        "missing_formation_csv": str(run_dir / "03_megnet_formation_energy" / "missing_formation_predictions.csv"),
        "candidates_csv": str(run_dir / "04_candidates_after_thresholds" / "candidates.csv"),
        "mobility_ranked_csv": str(run_dir / "05_alignn_mobility_rank" / "mobility_ranked_candidates.csv"),
        "topk_summary_csv": str(run_dir / "06_top10_cif" / "top10_candidates.csv"),
    },
}
(run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
print(json.dumps(manifest, indent=2, ensure_ascii=False))
PY

echo "[run_threshold_case] completed: ${RUN_DIR}"
