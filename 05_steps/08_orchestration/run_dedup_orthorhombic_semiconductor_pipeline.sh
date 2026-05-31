#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT_DIR}/00_project/paths.sh"
TOP_K_FROM_ENV="${TOP_K-}"
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
DEDUP_MODE="${DEDUP_MODE:-formula}"
DEDUP_LTOL="${DEDUP_LTOL:-0.2}"
DEDUP_STOL="${DEDUP_STOL:-0.3}"
DEDUP_ANGLE_TOL="${DEDUP_ANGLE_TOL:-5.0}"
DEDUP_REFERENCE_DIR="${DEDUP_REFERENCE_DIR:-${SOURCE_CIF_REFERENCE_ROOT}}"
BANDGAP_THRESHOLD="${DEDUP_CASE_BANDGAP_THRESHOLD:-${DEDUP_BANDGAP_THRESHOLD:-1.0}}"
FORMATION_ENERGY_THRESHOLD="${DEDUP_CASE_FORMATION_THRESHOLD:-${DEDUP_FORMATION_ENERGY_THRESHOLD:-0.0}}"
PHONONBENCH_IMAG_THRESHOLD="${PHONONBENCH_IMAG_THRESHOLD:-0.1}"
STRICT90_MAX_ANGLE_DEVIATION_DEG="${STRICT90_MAX_ANGLE_DEVIATION_DEG:-0.6}"
if [[ -n "${TOP_K_FROM_ENV}" ]]; then
  TOP_K="${TOP_K_FROM_ENV}"
fi
TOP_K="${TOP_K:-10}"
SYMPREC="${SYMPREC:-0.1}"
ANGLE_TOLERANCE="${ANGLE_TOLERANCE:-5.0}"
PHONONBENCH_DIM="${PHONONBENCH_DIM:-2 2 2}"
PHONONBENCH_GPU_LIST="${PHONONBENCH_GPU_LIST:-0}"
PHONONBENCH_SUBPARTS_PER_GPU="${PHONONBENCH_SUBPARTS_PER_GPU:-1}"
PHONONBENCH_MODEL="${PHONONBENCH_MODEL:-mattersim-v1}"
ALIGNN_MOBILITY_CONFIG_PATH="${ALIGNN_MOBILITY_MODEL_CONFIG_OVERRIDE:-${ALIGNN_MOBILITY_MODEL_CONFIG}}"
ALIGNN_MOBILITY_CHECKPOINT_PATH="${ALIGNN_MOBILITY_MODEL_CKPT_OVERRIDE:-${ALIGNN_MOBILITY_MODEL_CKPT}}"
TOPK_TOKEN="top${TOP_K}"

BG_TOKEN="$(format_threshold_token "${BANDGAP_THRESHOLD}")"
EFORM_TOKEN="$(format_threshold_token "${FORMATION_ENERGY_THRESHOLD}")"
PHONON_TOKEN="$(format_threshold_token "${PHONONBENCH_IMAG_THRESHOLD}")"
RUN_NAME="${RUN_NAME:-$(date +%Y%m%d)__from_${SOURCE_RUN_LABEL}__dedup_generated_and_source_cif__${TARGET_CRYSTAL_SYSTEM}__bg_gt_${BG_TOKEN}eV__eform_lt_${EFORM_TOKEN}eV_atom__phonon_stable_imag${PHONON_TOKEN}__mobility_rank__${TOPK_TOKEN}__strict90}"
RUN_ROOT="${RUN_ROOT:-${RUNS_ROOT}/${RUN_NAME}}"
RUN_LOG_DIR="${LOGS_BY_RUN_ROOT}/${RUN_NAME}"
ORCH_LOG_PATH="${RUN_LOG_DIR}/00_orchestration.log"

RUN_STEP01_DIR="${RUN_ROOT}/01_input_generated_cif"
RUN_STEP02_DIR="${RUN_ROOT}/02_structure_dedup"
RUN_STEP03_DIR="${RUN_ROOT}/03_orthorhombic_filter"
RUN_STEP04_DIR="${RUN_ROOT}/04_alignn_bandgap_screen"
RUN_STEP05_DIR="${RUN_ROOT}/05_megnet_formation_energy"
RUN_STEP06_DIR="${RUN_ROOT}/06_candidates_after_formation"
RUN_STEP07_DIR="${RUN_ROOT}/07_phononbench_stability"
RUN_STEP07B_DIR="${RUN_ROOT}/07b_postphonon_orthorhombic_filter"
RUN_STEP08_DIR="${RUN_ROOT}/08_alignn_mobility_rank"
RUN_STEP09_DIR="${RUN_ROOT}/09_${TOPK_TOKEN}_cif"
RUN_STEP10_DIR="${RUN_ROOT}/10_${TOPK_TOKEN}_strict90"

if [[ -e "${RUN_ROOT}" || -L "${RUN_ROOT}" ]]; then
  echo "[run_dedup_orthorhombic_semiconductor_pipeline] target run already exists: ${RUN_ROOT}" >&2
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
  "${RUN_STEP07_DIR}" \
  "${RUN_STEP07B_DIR}" \
  "${RUN_STEP08_DIR}" \
  "${RUN_STEP09_DIR}" \
  "${RUN_STEP10_DIR}"
exec > >(tee -a "${ORCH_LOG_PATH}") 2>&1

if [[ ! -d "${INPUT_SOURCE_DIR}" ]]; then
  echo "[run_dedup_orthorhombic_semiconductor_pipeline] missing input CIF dir: ${INPUT_SOURCE_DIR}" >&2
  exit 2
fi

ln -sfn "${INPUT_SOURCE_DIR}" "${RUN_STEP01_DIR}"

CONDA_BASE="${CONDA_BASE:-$(conda info --base)}"
# shellcheck disable=SC1091
source "${CONDA_BASE}/etc/profile.d/conda.sh"

echo "[run_dedup_orthorhombic_semiconductor_pipeline] step 02: ${DEDUP_MODE} deduplication"
conda activate diffcsp-gen
if [[ "${DEDUP_MODE}" == "formula" ]]; then
  python "${SCRIPT_DIR}/deduplicate_cifs_by_formula.py" \
    --input_dir "${RUN_STEP01_DIR}" \
    --history_dir "${DEDUP_REFERENCE_DIR}" \
    --output_dir "${RUN_STEP02_DIR}" | tee "${RUN_LOG_DIR}/02_structure_dedup.log"
  ln -sfn formula_unique_cif "${RUN_STEP02_DIR}/dedup_unique_cif"
  ln -sfn formula_unique_candidates.csv "${RUN_STEP02_DIR}/dedup_unique_candidates.csv"
  ln -sfn formula_all.csv "${RUN_STEP02_DIR}/dedup_all.csv"
  ln -sfn formula_failures.csv "${RUN_STEP02_DIR}/dedup_failures.csv"
  ln -sfn formula_summary.json "${RUN_STEP02_DIR}/dedup_summary.json"
  printf 'cluster_id,representative_cif_name,representative_cif_path,cluster_size,reduced_formula,num_sites,member_cif_names,matches_reference_dataset,matched_reference_cif_name,matched_reference_cif_path,kept_for_downstream,removal_reason\n' > "${RUN_STEP02_DIR}/dedup_clusters.csv"
elif [[ "${DEDUP_MODE}" == "structure" ]]; then
  python "${SCRIPT_DIR}/deduplicate_cifs_by_structure.py" \
    --input_dir "${RUN_STEP01_DIR}" \
    --reference_dir "${DEDUP_REFERENCE_DIR}" \
    --all_output_csv "${RUN_STEP02_DIR}/dedup_all.csv" \
    --selected_output_csv "${RUN_STEP02_DIR}/dedup_unique_candidates.csv" \
    --clusters_output_csv "${RUN_STEP02_DIR}/dedup_clusters.csv" \
    --failures_output_csv "${RUN_STEP02_DIR}/dedup_failures.csv" \
    --selected_cif_dir "${RUN_STEP02_DIR}/dedup_unique_cif" \
    --summary_json "${RUN_STEP02_DIR}/dedup_summary.json" \
    --ltol "${DEDUP_LTOL}" \
    --stol "${DEDUP_STOL}" \
    --angle_tol "${DEDUP_ANGLE_TOL}" | tee "${RUN_LOG_DIR}/02_structure_dedup.log"
else
  echo "[run_dedup_orthorhombic_semiconductor_pipeline] unknown DEDUP_MODE=${DEDUP_MODE}" >&2
  exit 2
fi

echo "[run_dedup_orthorhombic_semiconductor_pipeline] step 03: crystal-system filter"
python "${SCRIPT_DIR}/filter_cifs_by_crystal_system.py" \
  --input_dir "${RUN_STEP02_DIR}/dedup_unique_cif" \
  --all_output_csv "${RUN_STEP03_DIR}/crystal_system_all.csv" \
  --selected_output_csv "${RUN_STEP03_DIR}/orthorhombic_candidates.csv" \
  --failures_output_csv "${RUN_STEP03_DIR}/parse_failures.csv" \
  --selected_cif_dir "${RUN_STEP03_DIR}/orthorhombic_cif" \
  --summary_json "${RUN_STEP03_DIR}/orthorhombic_summary.json" \
  --target_crystal_system "${TARGET_CRYSTAL_SYSTEM}" \
  --symprec "${SYMPREC}" \
  --angle_tolerance "${ANGLE_TOLERANCE}" | tee "${RUN_LOG_DIR}/03_orthorhombic_filter.log"
conda deactivate

echo "[run_dedup_orthorhombic_semiconductor_pipeline] step 04: bandgap screening"
RUN_ID="${RUN_NAME}" \
ALIGNN_CIF_INPUT_DIR="${RUN_STEP03_DIR}/orthorhombic_cif" \
CASE_ALIGNN_BANDGAP_THRESHOLD="${BANDGAP_THRESHOLD}" \
ALIGNN_BANDGAP_OUTPUT_CSV="${RUN_STEP04_DIR}/bandgap_predictions.csv" \
ALIGNN_NONMETAL_OUTPUT_CSV="${RUN_STEP04_DIR}/nonmetal_candidates.csv" \
ALIGNN_BANDGAP_LOG_PATH="${RUN_LOG_DIR}/04_alignn_bandgap_screen.log" \
bash "${STEP04_DIR}/run.sh"

echo "[run_dedup_orthorhombic_semiconductor_pipeline] step 04b: materialize nonmetal CIF folder"
python - "${RUN_STEP04_DIR}/nonmetal_candidates.csv" "${RUN_STEP04_DIR}/nonmetal_cif" <<'PY'
import csv
import os
import sys
from pathlib import Path

rows = []
with Path(sys.argv[1]).open("r", newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
out_dir = Path(sys.argv[2])
out_dir.mkdir(parents=True, exist_ok=True)
for child in out_dir.iterdir():
    if child.is_file() or child.is_symlink():
        child.unlink()
for row in rows:
    cif_path = Path(str(row.get("cif_path") or "")).resolve()
    if not cif_path.exists():
        continue
    dst = out_dir / cif_path.name
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    os.symlink(cif_path, dst)
print({"nonmetal_candidates": len(rows), "nonmetal_cif_dir": str(out_dir)})
PY

echo "[run_dedup_orthorhombic_semiconductor_pipeline] step 05: formation-energy prediction"
RUN_ID="${RUN_NAME}" \
MEGNET_INPUT_CSV="${RUN_STEP04_DIR}/nonmetal_candidates.csv" \
MEGNET_INPUT_CIF_DIR="${RUN_STEP04_DIR}/nonmetal_cif" \
MEGNET_OUTPUT_CSV="${RUN_STEP05_DIR}/formation_energy_predictions.csv" \
MEGNET_LOG_PATH="${RUN_LOG_DIR}/05_megnet_formation_energy.log" \
bash "${STEP05_DIR}/run.sh"

echo "[run_dedup_orthorhombic_semiconductor_pipeline] step 06: formation-energy filtering"
python "${SCRIPT_DIR}/filter_candidates_by_formation_energy.py" \
  --run_id "${RUN_NAME}" \
  --source_input_dir "${RUN_STEP04_DIR}/nonmetal_cif" \
  --formation_csv "${RUN_STEP05_DIR}/formation_energy_predictions.csv" \
  --merged_output_csv "${RUN_STEP05_DIR}/formation_energy_merged.csv" \
  --missing_output_csv "${RUN_STEP05_DIR}/missing_formation_predictions.csv" \
  --selected_output_csv "${RUN_STEP06_DIR}/formation_selected_candidates.csv" \
  --selected_cif_dir "${RUN_STEP06_DIR}/formation_selected_cif" \
  --summary_json "${RUN_STEP06_DIR}/formation_summary.json" \
  --formation_threshold "${FORMATION_ENERGY_THRESHOLD}" | tee "${RUN_LOG_DIR}/06_candidates_after_formation.log"

echo "[run_dedup_orthorhombic_semiconductor_pipeline] step 07: phononbench dynamical-stability screening"
RUN_ID="${RUN_NAME}" \
PHONONBENCH_INPUT_CIF_DIR="${RUN_STEP06_DIR}/formation_selected_cif" \
PHONONBENCH_PHONOPY_INPUT_DIR="${RUN_STEP07_DIR}/phonopy_inputs" \
PHONONBENCH_OUTPUT_DIR="${RUN_STEP07_DIR}/phonon_output" \
PHONONBENCH_RELAXED_DIR="${RUN_STEP07_DIR}/relaxed" \
PHONONBENCH_ALL_OUTPUT_CSV="${RUN_STEP07_DIR}/phonon_stability_all.csv" \
PHONONBENCH_STABLE_OUTPUT_CSV="${RUN_STEP07_DIR}/phonon_stable_candidates.csv" \
PHONONBENCH_STABLE_CIF_DIR="${RUN_STEP07_DIR}/stable_relaxed_cif" \
PHONONBENCH_SUMMARY_JSON="${RUN_STEP07_DIR}/phonon_stability_summary.json" \
PHONONBENCH_LOG_PATH="${RUN_LOG_DIR}/07_phononbench_stability.log" \
PHONONBENCH_DIM="${PHONONBENCH_DIM}" \
PHONONBENCH_GPU_LIST="${PHONONBENCH_GPU_LIST}" \
PHONONBENCH_SUBPARTS_PER_GPU="${PHONONBENCH_SUBPARTS_PER_GPU}" \
PHONONBENCH_MODEL="${PHONONBENCH_MODEL}" \
PHONONBENCH_IMAG_THRESHOLD="${PHONONBENCH_IMAG_THRESHOLD}" \
bash "${STEP05B_DIR}/run.sh"

echo "[run_dedup_orthorhombic_semiconductor_pipeline] step 07b: post-phonon orthorhombic guard"
conda activate diffcsp-gen
python "${SCRIPT_DIR}/filter_cifs_by_crystal_system.py" \
  --input_dir "${RUN_STEP07_DIR}/stable_relaxed_cif" \
  --all_output_csv "${RUN_STEP07B_DIR}/postphonon_crystal_system_all.csv" \
  --selected_output_csv "${RUN_STEP07B_DIR}/postphonon_orthorhombic_candidates.csv" \
  --failures_output_csv "${RUN_STEP07B_DIR}/postphonon_parse_failures.csv" \
  --selected_cif_dir "${RUN_STEP07B_DIR}/postphonon_orthorhombic_cif" \
  --summary_json "${RUN_STEP07B_DIR}/postphonon_orthorhombic_summary.json" \
  --target_crystal_system "${TARGET_CRYSTAL_SYSTEM}" \
  --symprec "${SYMPREC}" \
  --angle_tolerance "${ANGLE_TOLERANCE}" | tee "${RUN_LOG_DIR}/07b_postphonon_orthorhombic_filter.log"
conda deactivate

python - "${RUN_STEP07_DIR}/phonon_stable_candidates.csv" "${RUN_STEP07B_DIR}/postphonon_orthorhombic_candidates.csv" "${RUN_STEP07B_DIR}/phonon_stable_orthorhombic_candidates.csv" "${RUN_STEP07B_DIR}/postphonon_orthorhombic_filter_summary.json" <<'PY'
import csv
import json
import sys
from pathlib import Path


def read_rows(path):
    with Path(path).open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


phonon_rows = read_rows(sys.argv[1])
selected_rows = read_rows(sys.argv[2])
selected_names = {str(row.get("cif_name") or "").strip() for row in selected_rows}
filtered_rows = [row for row in phonon_rows if str(row.get("cif_name") or "").strip() in selected_names]

fieldnames = list(phonon_rows[0].keys()) if phonon_rows else []
with Path(sys.argv[3]).open("w", newline="", encoding="utf-8") as csv_file:
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(filtered_rows)

summary = {
    "phonon_stable_csv": str(Path(sys.argv[1]).resolve()),
    "postphonon_orthorhombic_csv": str(Path(sys.argv[2]).resolve()),
    "output_csv": str(Path(sys.argv[3]).resolve()),
    "counts": {
        "phonon_stable_rows": len(phonon_rows),
        "postphonon_orthorhombic_rows": len(filtered_rows),
        "excluded_non_orthorhombic_rows": len(phonon_rows) - len(filtered_rows),
    },
}
Path(sys.argv[4]).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2, ensure_ascii=False))
PY

echo "[run_dedup_orthorhombic_semiconductor_pipeline] step 08: build mobility-rank input"
python "${SCRIPT_DIR}/build_mobility_rank_input.py" \
  --bandgap-csv "${RUN_STEP04_DIR}/nonmetal_candidates.csv" \
  --formation-selected-csv "${RUN_STEP06_DIR}/formation_selected_candidates.csv" \
  --phonon-stable-csv "${RUN_STEP07B_DIR}/phonon_stable_orthorhombic_candidates.csv" \
  --output-csv "${RUN_STEP08_DIR}/mobility_rank_input.csv" \
  --summary-json "${RUN_STEP08_DIR}/mobility_rank_input_summary.json" | tee "${RUN_LOG_DIR}/08_mobility_rank_input.log"

echo "[run_dedup_orthorhombic_semiconductor_pipeline] step 09: mobility ranking"
conda activate alignn-screen
python "${STEP06_DIR}/predict_alignn_mobility.py" \
  --model_config_path "${ALIGNN_MOBILITY_CONFIG_PATH}" \
  --checkpoint_path "${ALIGNN_MOBILITY_CHECKPOINT_PATH}" \
  --input_csv "${RUN_STEP08_DIR}/mobility_rank_input.csv" \
  --output_csv "${RUN_STEP08_DIR}/mobility_predictions.csv" \
  --ranked_output_csv "${RUN_STEP08_DIR}/mobility_ranked_candidates.csv" \
  --log_path "${RUN_LOG_DIR}/09_alignn_mobility_rank.log"
conda deactivate

echo "[run_dedup_orthorhombic_semiconductor_pipeline] step 10: ${TOPK_TOKEN} export"
RUN_ID="${RUN_NAME}" \
RANKED_CSV="${RUN_STEP08_DIR}/mobility_ranked_candidates.csv" \
OUTPUT_DIR="${RUN_STEP09_DIR}" \
SUMMARY_CSV="${RUN_STEP09_DIR}/${TOPK_TOKEN}_candidates.csv" \
TOP_K="${TOP_K}" \
LOG_PATH="${RUN_LOG_DIR}/10_${TOPK_TOKEN}_cif.log" \
bash "${STEP07_DIR}/run.sh"

echo "[run_dedup_orthorhombic_semiconductor_pipeline] step 11: strict 90-degree snap for ${TOPK_TOKEN}"
conda activate diffcsp-gen
python "${SCRIPT_DIR}/snap_near_orthorhombic_to_strict90.py" \
  --input_dir "${RUN_STEP09_DIR}" \
  --output_dir "${RUN_STEP10_DIR}/strict90_cif" \
  --summary_csv "${RUN_STEP10_DIR}/strict90_summary.csv" \
  --summary_json "${RUN_STEP10_DIR}/strict90_summary.json" \
  --target_crystal_system "${TARGET_CRYSTAL_SYSTEM}" \
  --max_angle_deviation_deg "${STRICT90_MAX_ANGLE_DEVIATION_DEG}" \
  --symprec "${SYMPREC}" \
  --angle_tolerance "${ANGLE_TOLERANCE}" | tee "${RUN_LOG_DIR}/11_${TOPK_TOKEN}_strict90.log"
conda deactivate

python - "${RUN_STEP09_DIR}/${TOPK_TOKEN}_candidates.csv" "${RUN_STEP10_DIR}/strict90_summary.csv" "${RUN_STEP10_DIR}/${TOPK_TOKEN}_candidates_strict90.csv" <<'PY'
import csv
import sys
from pathlib import Path


def read_rows(path):
    with Path(path).open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


top_rows = read_rows(sys.argv[1])
strict_rows = read_rows(sys.argv[2])
strict_by_name = {row["cif_name"]: row for row in strict_rows}

merged_rows = []
for row in top_rows:
    strict_row = strict_by_name.get(Path(row["copied_cif"]).name, {})
    merged = dict(row)
    merged["strict90_cif_path"] = strict_row.get("output_cif_path", "")
    merged["strict90_written"] = strict_row.get("written", "")
    merged["strict90_max_angle_deviation_deg"] = strict_row.get("max_angle_deviation_deg", "")
    merged["strict90_max_cartesian_shift_ang"] = strict_row.get("max_cartesian_shift_ang", "")
    merged_rows.append(merged)

fieldnames = list(merged_rows[0].keys()) if merged_rows else [
    "rank",
    "cif_name",
    "copied_cif",
    "strict90_cif_path",
]
with Path(sys.argv[3]).open("w", newline="", encoding="utf-8") as csv_file:
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(merged_rows)
PY

echo "[run_dedup_orthorhombic_semiconductor_pipeline] writing manifest"
python - "${RUN_NAME}" "${SOURCE_RUN_ID}" "${SOURCE_RUN_LABEL}" "${INPUT_SOURCE_DIR}" "${DEDUP_REFERENCE_DIR}" "${TARGET_CRYSTAL_SYSTEM}" "${BANDGAP_THRESHOLD}" "${FORMATION_ENERGY_THRESHOLD}" "${PHONONBENCH_IMAG_THRESHOLD}" "${SYMPREC}" "${ANGLE_TOLERANCE}" "${TOP_K}" "${RUN_ROOT}" "${RUN_LOG_DIR}" "${ALIGNN_MOBILITY_CONFIG_PATH}" "${ALIGNN_MOBILITY_CHECKPOINT_PATH}" "${PHONONBENCH_DIM}" "${PHONONBENCH_GPU_LIST}" "${PHONONBENCH_SUBPARTS_PER_GPU}" "${PHONONBENCH_MODEL}" <<'PY'
import csv
import json
import sys
from pathlib import Path


def read_csv_rows(path: Path):
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def read_json(path: Path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


run_name = sys.argv[1]
source_run_id = sys.argv[2]
source_run_label = sys.argv[3]
source_input_dir = sys.argv[4]
reference_dedup_dir = sys.argv[5]
target_crystal_system = sys.argv[6]
bandgap_threshold = float(sys.argv[7])
formation_threshold = float(sys.argv[8])
phonon_imag_threshold = float(sys.argv[9])
symprec = float(sys.argv[10])
angle_tolerance = float(sys.argv[11])
top_k = int(sys.argv[12])
run_root = Path(sys.argv[13])
run_log_dir = sys.argv[14]
alignn_config = sys.argv[15]
alignn_ckpt = sys.argv[16]
phonon_dim = sys.argv[17]
phonon_gpu_list = sys.argv[18]
phonon_subparts = sys.argv[19]
phonon_model = sys.argv[20]

step02 = run_root / "02_structure_dedup"
step03 = run_root / "03_orthorhombic_filter"
step04 = run_root / "04_alignn_bandgap_screen"
step05 = run_root / "05_megnet_formation_energy"
step06 = run_root / "06_candidates_after_formation"
step07 = run_root / "07_phononbench_stability"
step07b = run_root / "07b_postphonon_orthorhombic_filter"
step08 = run_root / "08_alignn_mobility_rank"
step09 = next(run_root.glob("09_*_cif"))
step10 = next(run_root.glob("10_*_strict90"))

topk_csv = next(step09.glob("*_candidates.csv"), step09 / "top_candidates.csv")
strict90_merged_csv = next(step10.glob("*_candidates_strict90.csv"), step10 / "top_candidates_strict90.csv")
strict90_summary = read_json(step10 / "strict90_summary.json")
manifest = {
    "run_id": run_name,
    "source_run_id": source_run_id,
    "source_run_label": source_run_label,
    "source_input_dir": source_input_dir,
    "reference_dedup_dir": reference_dedup_dir,
    "target_crystal_system": target_crystal_system,
    "thresholds": {
        "bandgap_gt_eV": bandgap_threshold,
        "formation_lt_eV_per_atom": formation_threshold,
        "phonon_imag_threshold": phonon_imag_threshold,
        "strict90_max_angle_deviation_deg": strict90_summary.get("max_angle_deviation_deg", None),
        "symprec": symprec,
        "angle_tolerance": angle_tolerance,
        "top_k": top_k,
    },
    "model_paths": {
        "alignn_mobility_config": alignn_config,
        "alignn_mobility_checkpoint": alignn_ckpt,
    },
    "phononbench": {
        "dim": phonon_dim,
        "gpu_list": phonon_gpu_list,
        "subparts_per_gpu": phonon_subparts,
        "model": phonon_model,
    },
    "counts": {
        "source_input_cif_total": len(list((run_root / "01_input_generated_cif").glob("*.cif"))) if (run_root / "01_input_generated_cif").exists() else 0,
        "dedup_unique_count": len(read_csv_rows(step02 / "dedup_unique_candidates.csv")),
        "orthorhombic_selected_count": len(read_csv_rows(step03 / "orthorhombic_candidates.csv")),
        "bandgap_pass_count": len(read_csv_rows(step04 / "nonmetal_candidates.csv")),
        "formation_selected_count": len(read_csv_rows(step06 / "formation_selected_candidates.csv")),
        "phonon_stable_count": len(read_csv_rows(step07 / "phonon_stable_candidates.csv")),
        "postphonon_orthorhombic_count": len(read_csv_rows(step07b / "phonon_stable_orthorhombic_candidates.csv")),
        "mobility_ranked_candidates": len(read_csv_rows(step08 / "mobility_ranked_candidates.csv")),
        "topk_candidates": len(read_csv_rows(topk_csv)),
        "topk_strict90_written_count": sum(1 for row in read_csv_rows(strict90_merged_csv) if str(row.get("strict90_written") or "").strip().lower() in {"1", "true", "yes", "y"}),
    },
    "paths": {
        "run_root": str(run_root),
        "run_log_dir": run_log_dir,
        "dedup_summary_json": str(step02 / "dedup_summary.json"),
        "orthorhombic_summary_json": str(step03 / "orthorhombic_summary.json"),
        "formation_summary_json": str(step06 / "formation_summary.json"),
        "phonon_stability_summary_json": str(step07 / "phonon_stability_summary.json"),
        "postphonon_orthorhombic_summary_json": str(step07b / "postphonon_orthorhombic_summary.json"),
        "postphonon_orthorhombic_filter_summary_json": str(step07b / "postphonon_orthorhombic_filter_summary.json"),
        "mobility_rank_input_summary_json": str(step08 / "mobility_rank_input_summary.json"),
        "strict90_summary_json": str(step10 / "strict90_summary.json"),
        "mobility_ranked_csv": str(step08 / "mobility_ranked_candidates.csv"),
        "topk_csv": str(topk_csv),
        "topk_strict90_csv": str(strict90_merged_csv),
    },
}
(run_root / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(manifest, indent=2, ensure_ascii=False))
PY

echo "[run_dedup_orthorhombic_semiconductor_pipeline] completed: ${RUN_ROOT}"
