#!/usr/bin/env python3
import argparse
import csv
import json
import os
from pathlib import Path


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


def count_input_cifs(path: Path):
    return sum(1 for _ in path.rglob("*.cif"))


def main():
    parser = argparse.ArgumentParser(
        description="Build one explicit threshold-screening case from bandgap and formation-energy predictions."
    )
    parser.add_argument("--run_id", required=True)
    parser.add_argument("--source_input_dir", required=True)
    parser.add_argument("--bandgap_csv", required=True)
    parser.add_argument("--formation_csv", required=True)
    parser.add_argument("--merged_output_csv", required=True)
    parser.add_argument("--missing_output_csv", required=True)
    parser.add_argument("--candidates_output_csv", required=True)
    parser.add_argument("--summary_json", required=True)
    parser.add_argument("--bandgap_threshold", type=float, required=True)
    parser.add_argument("--formation_threshold", type=float, required=True)
    args = parser.parse_args()

    source_input_dir = Path(args.source_input_dir)
    bandgap_rows = read_csv_rows(Path(args.bandgap_csv))
    formation_rows = read_csv_rows(Path(args.formation_csv))

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

    for row in bandgap_rows:
        cif_path = row["cif_path"]
        cif_name = row.get("cif_name") or Path(cif_path).name
        formation_row = formation_by_path.get(cif_path)
        if formation_row is None:
            formation_row = formation_by_realpath.get(os.path.realpath(cif_path))
        if formation_row is None:
            formation_row = formation_by_name.get(cif_name)

        bandgap = to_float(row.get("bandgap"))
        formation_energy = (
            to_float(formation_row.get("formation_energy")) if formation_row is not None else None
        )
        passes_bandgap = bandgap is not None and bandgap > args.bandgap_threshold
        passes_formation = (
            formation_energy is not None and formation_energy < args.formation_threshold
        )
        selected = passes_bandgap and passes_formation

        merged = {
            "cif_name": cif_name,
            "cif_path": cif_path,
            "bandgap": row.get("bandgap", ""),
            "formation_energy": (
                formation_row.get("formation_energy", "") if formation_row is not None else ""
            ),
            "passes_bandgap_filter": passes_bandgap,
            "passes_formation_filter": passes_formation,
            "selected_for_mobility": selected,
        }
        merged_rows.append(merged)

        if formation_row is None:
            missing_rows.append(
                {
                    "cif_name": cif_name,
                    "cif_path": cif_path,
                    "bandgap": row.get("bandgap", ""),
                }
            )

        if selected:
            selected_rows.append(dict(merged))

    fieldnames = [
        "cif_name",
        "cif_path",
        "bandgap",
        "formation_energy",
        "passes_bandgap_filter",
        "passes_formation_filter",
        "selected_for_mobility",
    ]
    write_csv(Path(args.merged_output_csv), fieldnames, merged_rows)
    write_csv(
        Path(args.missing_output_csv),
        ["cif_name", "cif_path", "bandgap"],
        missing_rows,
    )
    write_csv(Path(args.candidates_output_csv), fieldnames, selected_rows)

    summary = {
        "run_id": args.run_id,
        "source_input_dir": str(source_input_dir),
        "bandgap_threshold_ev": args.bandgap_threshold,
        "formation_threshold_ev_per_atom": args.formation_threshold,
        "counts": {
            "input_cif_total": count_input_cifs(source_input_dir),
            "bandgap_predictions_total": len(bandgap_rows),
            "bandgap_pass_count": sum(1 for row in merged_rows if row["passes_bandgap_filter"]),
            "formation_predictions_total": len(formation_rows),
            "matched_formation_rows": sum(
                1 for row in merged_rows if row["formation_energy"] != ""
            ),
            "missing_formation_rows": len(missing_rows),
            "selected_candidates": len(selected_rows),
        },
        "paths": {
            "merged_output_csv": args.merged_output_csv,
            "missing_output_csv": args.missing_output_csv,
            "candidates_output_csv": args.candidates_output_csv,
        },
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
