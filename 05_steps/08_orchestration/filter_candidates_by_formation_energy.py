#!/usr/bin/env python3
import argparse
import csv
import json
import os
from pathlib import Path


def list_cifs(path: Path):
    return sorted(path.glob("*.cif"))


def read_csv_rows(path: Path):
    with path.open("r", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def to_float(value):
    try:
        return float(value)
    except Exception:
        return None


def safe_unlink(path: Path):
    if path.exists() or path.is_symlink():
        path.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Filter candidates by formation energy and export a clean CIF directory for downstream phonon screening."
    )
    parser.add_argument("--run_id", required=True)
    parser.add_argument("--source_input_dir", required=True)
    parser.add_argument("--formation_csv", required=True)
    parser.add_argument("--merged_output_csv", required=True)
    parser.add_argument("--missing_output_csv", required=True)
    parser.add_argument("--selected_output_csv", required=True)
    parser.add_argument("--selected_cif_dir", required=True)
    parser.add_argument("--summary_json", required=True)
    parser.add_argument("--formation_threshold", type=float, required=True)
    args = parser.parse_args()

    source_input_dir = Path(args.source_input_dir)
    formation_rows = read_csv_rows(Path(args.formation_csv))
    selected_cif_dir = Path(args.selected_cif_dir)
    selected_cif_dir.mkdir(parents=True, exist_ok=True)
    for child in selected_cif_dir.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()

    formation_by_path = {}
    formation_by_realpath = {}
    formation_by_name = {}
    for row in formation_rows:
        cif_path = row.get("cif_path", "")
        if cif_path:
            formation_by_path[cif_path] = row
            formation_by_realpath[os.path.realpath(cif_path)] = row
        file_name = row.get("file_name")
        if file_name:
            formation_by_name[file_name] = row

    merged_rows = []
    missing_rows = []
    selected_rows = []

    for cif_path in list_cifs(source_input_dir):
        formation_row = formation_by_path.get(str(cif_path.resolve()))
        if formation_row is None:
            formation_row = formation_by_realpath.get(os.path.realpath(cif_path))
        if formation_row is None:
            formation_row = formation_by_name.get(cif_path.name)

        formation_energy = (
            to_float(formation_row.get("formation_energy")) if formation_row is not None else None
        )
        passes_formation = (
            formation_energy is not None and formation_energy < args.formation_threshold
        )
        selected_cif_path = ""
        if passes_formation:
            linked_cif = selected_cif_dir / cif_path.name
            safe_unlink(linked_cif)
            linked_cif.symlink_to(cif_path.resolve())
            selected_cif_path = str(linked_cif)

        merged = {
            "cif_name": cif_path.name,
            "cif_path": str(cif_path.resolve()),
            "formation_energy": (
                formation_row.get("formation_energy", "") if formation_row is not None else ""
            ),
            "passes_formation_filter": passes_formation,
            "selected_for_phonon": passes_formation,
            "selected_cif_path": selected_cif_path,
        }
        merged_rows.append(merged)

        if formation_row is None:
            missing_rows.append(
                {
                    "cif_name": cif_path.name,
                    "cif_path": str(cif_path.resolve()),
                }
            )

        if passes_formation:
            selected_rows.append(dict(merged))

    fieldnames = [
        "cif_name",
        "cif_path",
        "formation_energy",
        "passes_formation_filter",
        "selected_for_phonon",
        "selected_cif_path",
    ]
    write_csv(Path(args.merged_output_csv), fieldnames, merged_rows)
    write_csv(Path(args.missing_output_csv), ["cif_name", "cif_path"], missing_rows)
    write_csv(Path(args.selected_output_csv), fieldnames, selected_rows)

    summary = {
        "run_id": args.run_id,
        "source_input_dir": str(source_input_dir),
        "formation_threshold_ev_per_atom": args.formation_threshold,
        "counts": {
            "input_cif_total": len(merged_rows),
            "formation_predictions_total": len(formation_rows),
            "matched_formation_rows": sum(1 for row in merged_rows if row["formation_energy"] != ""),
            "missing_formation_rows": len(missing_rows),
            "selected_candidates": len(selected_rows),
        },
        "paths": {
            "merged_output_csv": args.merged_output_csv,
            "missing_output_csv": args.missing_output_csv,
            "selected_output_csv": args.selected_output_csv,
            "selected_cif_dir": str(selected_cif_dir),
        },
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
