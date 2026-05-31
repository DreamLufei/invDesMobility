#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "00_project"))

from paths import RUNS_ROOT  # noqa: E402


def read_csv_rows(path: Path):
    with path.open("r", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def to_float(value):
    try:
        return float(value)
    except Exception:
        return None


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Merge bandgap and formation-energy results, then filter by formation energy."
    )
    parser.add_argument(
        "--bandgap_csv",
        default=str(RUNS_ROOT / "adhoc_bandgap_screen" / "02_alignn_bandgap_nonmetal" / "nonmetal_candidates.csv"),
    )
    parser.add_argument(
        "--formation_csv",
        default=str(RUNS_ROOT / "adhoc_bandgap_screen" / "03_megnet_formation_energy" / "formation_energy_predictions.csv"),
    )
    parser.add_argument(
        "--all_output_csv",
        default=str(RUNS_ROOT / "adhoc_bandgap_screen" / "03_megnet_formation_energy" / "formation_energy_merged.csv"),
    )
    parser.add_argument(
        "--selected_output_csv",
        default=str(RUNS_ROOT / "adhoc_bandgap_screen" / "03_megnet_formation_energy" / "formation_energy_selected.csv"),
    )
    parser.add_argument("--formation_threshold", type=float, default=0.0)
    args = parser.parse_args()

    bandgap_rows = read_csv_rows(Path(args.bandgap_csv))
    formation_rows = read_csv_rows(Path(args.formation_csv))
    bandgap_by_path = {row["cif_path"]: row for row in bandgap_rows}

    merged_rows = []
    selected_rows = []
    for row in formation_rows:
        cif_path = row["cif_path"]
        bandgap_row = bandgap_by_path.get(cif_path, {})
        formation_energy = to_float(row.get("formation_energy"))
        passes_formation = (
            formation_energy is not None and formation_energy <= args.formation_threshold
        )
        merged = {
            "cif_name": bandgap_row.get("cif_name") or row.get("file_name") or Path(cif_path).name,
            "cif_path": cif_path,
            "bandgap": bandgap_row.get("bandgap", ""),
            "is_nonmetal": bandgap_row.get("is_nonmetal", ""),
            "formation_energy": row.get("formation_energy", ""),
            "passes_formation_filter": passes_formation,
        }
        merged_rows.append(merged)
        if passes_formation:
            selected_rows.append(merged)

    fieldnames = [
        "cif_name",
        "cif_path",
        "bandgap",
        "is_nonmetal",
        "formation_energy",
        "passes_formation_filter",
    ]
    write_csv(Path(args.all_output_csv), fieldnames, merged_rows)
    write_csv(Path(args.selected_output_csv), fieldnames, selected_rows)
    print(
        {
            "all_candidates": len(merged_rows),
            "selected_candidates": len(selected_rows),
            "formation_threshold": args.formation_threshold,
            "all_output_csv": args.all_output_csv,
            "selected_output_csv": args.selected_output_csv,
        }
    )


if __name__ == "__main__":
    main()
