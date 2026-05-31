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


def safe_unlink(path: Path):
    if path.exists() or path.is_symlink():
        path.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Create a clean CIF directory from a CSV containing cif_path entries."
    )
    parser.add_argument("--input_csv", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--summary_csv", required=True)
    parser.add_argument("--summary_json", required=True)
    args = parser.parse_args()

    rows = read_csv_rows(Path(args.input_csv))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for child in output_dir.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()

    linked_rows = []
    for row in rows:
        src = Path(row["cif_path"])
        dst = output_dir / src.name
        safe_unlink(dst)
        dst.symlink_to(src.resolve())
        merged = dict(row)
        merged["linked_cif_path"] = str(dst)
        linked_rows.append(merged)

    fieldnames = list(linked_rows[0].keys()) if linked_rows else ["cif_path", "linked_cif_path"]
    write_csv(Path(args.summary_csv), fieldnames, linked_rows)

    summary = {
        "input_csv": args.input_csv,
        "output_dir": args.output_dir,
        "counts": {
            "input_rows": len(rows),
            "linked_cif_total": len(linked_rows),
        },
        "paths": {
            "summary_csv": args.summary_csv,
        },
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
