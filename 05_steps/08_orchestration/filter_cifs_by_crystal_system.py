#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
import sys

from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def list_cifs(path: Path):
    return sorted(path.glob("*.cif"))


def safe_unlink(path: Path):
    if path.exists() or path.is_symlink():
        path.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Filter generated CIFs by crystal system and build a clean subset directory."
    )
    parser.add_argument("--input_dir", required=True)
    parser.add_argument("--all_output_csv", required=True)
    parser.add_argument("--selected_output_csv", required=True)
    parser.add_argument("--failures_output_csv", required=True)
    parser.add_argument("--selected_cif_dir", required=True)
    parser.add_argument("--summary_json", required=True)
    parser.add_argument("--target_crystal_system", default="orthorhombic")
    parser.add_argument("--symprec", type=float, default=0.1)
    parser.add_argument("--angle_tolerance", type=float, default=5.0)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    selected_cif_dir = Path(args.selected_cif_dir)
    selected_cif_dir.mkdir(parents=True, exist_ok=True)

    # Keep reruns deterministic inside a dedicated run directory.
    for child in selected_cif_dir.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()

    target = args.target_crystal_system.lower()
    all_rows = []
    selected_rows = []
    failure_rows = []

    for cif_path in list_cifs(input_dir):
        row = {
            "cif_name": cif_path.name,
            "cif_path": str(cif_path.resolve()),
            "target_crystal_system": target,
            "crystal_system": "",
            "space_group_symbol": "",
            "space_group_number": "",
            "is_target_crystal_system": False,
            "parse_ok": False,
            "error": "",
        }
        try:
            structure = Structure.from_file(cif_path)
            analyzer = SpacegroupAnalyzer(
                structure,
                symprec=args.symprec,
                angle_tolerance=args.angle_tolerance,
            )
            crystal_system = analyzer.get_crystal_system()
            row["crystal_system"] = crystal_system
            row["space_group_symbol"] = analyzer.get_space_group_symbol()
            row["space_group_number"] = analyzer.get_space_group_number()
            row["parse_ok"] = True
            row["is_target_crystal_system"] = crystal_system.lower() == target

            if row["is_target_crystal_system"]:
                link_path = selected_cif_dir / cif_path.name
                safe_unlink(link_path)
                link_path.symlink_to(cif_path.resolve())
                selected_rows.append(
                    {
                        "cif_name": cif_path.name,
                        "cif_path": str(link_path),
                        "source_cif_path": str(cif_path.resolve()),
                        "crystal_system": crystal_system,
                        "space_group_symbol": row["space_group_symbol"],
                        "space_group_number": row["space_group_number"],
                    }
                )
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            failure_rows.append(
                {
                    "cif_name": cif_path.name,
                    "cif_path": str(cif_path.resolve()),
                    "error": row["error"],
                }
            )
        all_rows.append(row)

    write_csv(
        Path(args.all_output_csv),
        [
            "cif_name",
            "cif_path",
            "target_crystal_system",
            "crystal_system",
            "space_group_symbol",
            "space_group_number",
            "is_target_crystal_system",
            "parse_ok",
            "error",
        ],
        all_rows,
    )
    write_csv(
        Path(args.selected_output_csv),
        [
            "cif_name",
            "cif_path",
            "source_cif_path",
            "crystal_system",
            "space_group_symbol",
            "space_group_number",
        ],
        selected_rows,
    )
    write_csv(
        Path(args.failures_output_csv),
        ["cif_name", "cif_path", "error"],
        failure_rows,
    )

    summary = {
        "input_dir": str(input_dir),
        "target_crystal_system": target,
        "symprec": args.symprec,
        "angle_tolerance": args.angle_tolerance,
        "counts": {
            "input_cif_total": len(all_rows),
            "parse_success": sum(1 for row in all_rows if row["parse_ok"]),
            "parse_failures": len(failure_rows),
            "selected_cif_total": len(selected_rows),
        },
        "paths": {
            "all_output_csv": args.all_output_csv,
            "selected_output_csv": args.selected_output_csv,
            "failures_output_csv": args.failures_output_csv,
            "selected_cif_dir": args.selected_cif_dir,
        },
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
