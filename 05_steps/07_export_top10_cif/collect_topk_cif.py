#!/usr/bin/env python3
import argparse
import csv
import shutil
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


def main():
    parser = argparse.ArgumentParser(description="Copy top-k ranked CIFs into a clean folder.")
    parser.add_argument("--ranked_csv", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--summary_csv", required=True)
    parser.add_argument("--top_k", type=int, default=10)
    args = parser.parse_args()

    rows = read_csv_rows(Path(args.ranked_csv))
    top_rows = rows[: args.top_k]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    for idx, row in enumerate(top_rows, start=1):
        src = Path(row["cif_path"])
        dst_name = f"rank_{idx:02d}__{src.name}"
        dst = output_dir / dst_name
        shutil.copy2(src, dst)
        merged = dict(row)
        merged["rank"] = idx
        merged["copied_cif"] = str(dst)
        summary_rows.append(merged)

    fieldnames = ["rank"] + [key for key in summary_rows[0].keys() if key != "rank"] if summary_rows else ["rank", "cif_path"]
    write_csv(Path(args.summary_csv), fieldnames, summary_rows)
    print(
        {
            "top_k": len(summary_rows),
            "output_dir": args.output_dir,
            "summary_csv": args.summary_csv,
        }
    )


if __name__ == "__main__":
    main()
