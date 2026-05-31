#!/usr/bin/env python3
import argparse
import csv
import json
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


def truthy(value):
    return str(value).strip().lower() in {"1", "true", "yes"}


def main():
    parser = argparse.ArgumentParser(
        description="Merge bandgap-pass candidates with strict90 outputs and prepare the mobility inference CSV."
    )
    parser.add_argument("--bandgap_csv", required=True)
    parser.add_argument("--strict90_csv", required=True)
    parser.add_argument("--output_csv", required=True)
    parser.add_argument("--missing_output_csv", required=True)
    parser.add_argument("--summary_json", required=True)
    args = parser.parse_args()

    bandgap_rows = read_csv_rows(Path(args.bandgap_csv))
    strict_rows = read_csv_rows(Path(args.strict90_csv))

    strict_by_name = {}
    for row in strict_rows:
        cif_name = Path(row.get("input_cif_path", "")).name
        if cif_name:
            strict_by_name[cif_name] = row

    selected_rows = []
    missing_rows = []
    for row in bandgap_rows:
        cif_name = row.get("cif_name") or Path(row["cif_path"]).name
        strict_row = strict_by_name.get(cif_name)
        if strict_row is None or not truthy(strict_row.get("written")):
            missing_rows.append(
                {
                    "cif_name": cif_name,
                    "cif_path": row["cif_path"],
                    "reason": "strict90_missing_or_not_written",
                }
            )
            continue

        merged = dict(row)
        merged["original_cif_path"] = row["cif_path"]
        merged["cif_path"] = strict_row["output_cif_path"]
        merged["strict90_cif_path"] = strict_row["output_cif_path"]
        merged["strict90_written"] = strict_row.get("written", "")
        merged["strict90_max_angle_deviation_deg"] = strict_row.get("max_angle_deviation_deg", "")
        merged["strict90_max_cartesian_shift_ang"] = strict_row.get("max_cartesian_shift_ang", "")
        selected_rows.append(merged)

    fieldnames = (
        list(selected_rows[0].keys())
        if selected_rows
        else [
            "cif_name",
            "cif_path",
            "bandgap",
            "is_nonmetal",
            "original_cif_path",
            "strict90_cif_path",
        ]
    )
    write_csv(Path(args.output_csv), fieldnames, selected_rows)
    write_csv(
        Path(args.missing_output_csv),
        ["cif_name", "cif_path", "reason"],
        missing_rows,
    )

    summary = {
        "bandgap_csv": args.bandgap_csv,
        "strict90_csv": args.strict90_csv,
        "counts": {
            "bandgap_pass_candidates": len(bandgap_rows),
            "mobility_input_candidates": len(selected_rows),
            "strict90_missing_or_failed": len(missing_rows),
        },
        "paths": {
            "output_csv": args.output_csv,
            "missing_output_csv": args.missing_output_csv,
        },
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
