#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/paths.sh"

RUN_ID="${1:-}"
if [[ -z "${RUN_ID}" ]]; then
  echo "Usage: bash ${SCRIPT_DIR}/show_pipeline_progress.sh <pipeline_run_id>" >&2
  exit 2
fi

RUN_ROOT="${RUNS_ROOT}/${RUN_ID}"
RUN_LOG_DIR="${LOGS_BY_RUN_ROOT}/${RUN_ID}"

echo "run_id=${RUN_ID}"
echo "run_root=${RUN_ROOT}"
echo "run_log_dir=${RUN_LOG_DIR}"
echo

python - "${RUN_ROOT}" <<'PY'
import csv
import json
import sys
from pathlib import Path

run_root = Path(sys.argv[1])

def read_json_count(path, key):
    path = Path(path)
    if not path.exists():
        return "pending"
    data = json.loads(path.read_text())
    cur = data
    for item in key:
        cur = cur[item]
    return cur

def count_csv_rows(path):
    path = Path(path)
    if not path.exists():
        return "pending"
    with path.open("r", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return len(rows)

items = [
    ("dedup_unique", run_root / "02_structure_dedup" / "dedup_summary.json", ("counts", "unique_cif_total"), "json"),
    ("orthorhombic_selected", run_root / "03_orthorhombic_filter" / "orthorhombic_summary.json", ("counts", "selected_cif_total"), "json"),
    ("formation_selected", run_root / "05_candidates_after_formation" / "formation_summary.json", ("counts", "selected_candidates"), "json"),
    ("phonon_stable", run_root / "06_phononbench_stability" / "phonon_stability_summary.json", ("counts", "stable_total"), "json"),
    ("bandgap_pass", run_root / "07_alignn_bandgap_screen" / "nonmetal_candidates.csv", None, "csv"),
    ("mobility_ranked", run_root / "08_alignn_mobility_rank" / "mobility_ranked_candidates.csv", None, "csv"),
    ("top10_exported", run_root / "09_top10_cif" / "top10_candidates.csv", None, "csv"),
    ("strict90_written", run_root / "10_top10_strict90" / "strict90_summary.json", ("counts", "written_cif_total"), "json"),
]

for label, path, key, mode in items:
    if mode == "json":
        value = read_json_count(path, key)
    else:
        value = count_csv_rows(path)
    print(f"{label}={value}")
PY

echo
echo "orchestration_log=${RUN_LOG_DIR}/00_orchestration.log"
echo "dedup_log=${RUN_LOG_DIR}/02_structure_dedup.log"
echo "orth_log=${RUN_LOG_DIR}/03_orthorhombic_filter.log"
echo "formation_log=${RUN_LOG_DIR}/04_megnet_formation_energy.log"
echo "formation_filter_log=${RUN_LOG_DIR}/05_candidates_after_formation.log"
echo "phonon_log=${RUN_LOG_DIR}/06_phononbench_stability.log"
echo "bandgap_log=${RUN_LOG_DIR}/07_alignn_bandgap_screen.log"
echo "mobility_log=${RUN_LOG_DIR}/08_alignn_mobility_rank.log"
echo "top10_log=${RUN_LOG_DIR}/09_top10_cif.log"
echo "strict90_log=${RUN_LOG_DIR}/10_top10_strict90.log"
