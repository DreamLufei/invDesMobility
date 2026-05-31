#!/usr/bin/env python3
import csv
import json
import os
from pathlib import Path
from statistics import mean, median
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "00_project"))

from paths import ALIGNN_MOBILITY_DATA_DIR, SOURCE_CIF_DIR  # noqa: E402


SOURCE_DIR = Path(os.environ.get("ALIGNN_MOBILITY_SOURCE_DIR", str(SOURCE_CIF_DIR))).resolve()
SOURCE_LABELS = Path(
    os.environ.get("ALIGNN_MOBILITY_SOURCE_LABELS", str(SOURCE_DIR / "id_prop.csv"))
).resolve()
OUTPUT_DIR = Path(
    os.environ.get("ALIGNN_MOBILITY_DATA_DIR_OVERRIDE", str(ALIGNN_MOBILITY_DATA_DIR))
).resolve()
OUTPUT_LABELS = OUTPUT_DIR / "id_prop.csv"
SUMMARY_PATH = Path(
    os.environ.get("ALIGNN_MOBILITY_SUMMARY_PATH", str(OUTPUT_DIR / "dataset_summary.json"))
).resolve()


def load_rows():
    with SOURCE_LABELS.open("r", newline="") as f:
        rows = list(csv.reader(f))

    if not rows:
        raise SystemExit(f"Empty label file: {SOURCE_LABELS}")

    first = rows[0]
    has_header = len(first) >= 2 and first[0].strip().lower() == "filename"
    if has_header:
        rows = rows[1:]

    cleaned = []
    for idx, row in enumerate(rows, start=1):
        if len(row) < 2:
            raise SystemExit(f"Row {idx} has fewer than 2 columns: {row}")
        filename = row[0].strip()
        try:
            target = float(row[1])
        except ValueError as exc:
            raise SystemExit(
                f"Row {idx} target is not numeric: filename={filename}, target={row[1]!r}"
            ) from exc
        cleaned.append((filename, target))
    return cleaned


def ensure_links(rows):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, _ in rows:
        src = SOURCE_DIR / filename
        dst = OUTPUT_DIR / filename
        if not src.exists():
            raise SystemExit(f"Missing CIF referenced by labels: {src}")
        if dst.is_symlink() or dst.exists():
            if dst.is_symlink() and dst.resolve() == src.resolve():
                continue
            dst.unlink()
        os.symlink(src, dst)


def write_labels(rows):
    with OUTPUT_LABELS.open("w", newline="") as f:
        writer = csv.writer(f)
        for filename, target in rows:
            writer.writerow([filename, f"{target:.6f}"])


def write_summary(rows):
    values = [target for _, target in rows]
    summary = {
        "source_dir": str(SOURCE_DIR),
        "source_labels": str(SOURCE_LABELS),
        "output_dir": str(OUTPUT_DIR),
        "output_labels": str(OUTPUT_LABELS),
        "n_samples": len(rows),
        "min_target": min(values),
        "max_target": max(values),
        "mean_target": mean(values),
        "median_target": median(values),
        "threshold_counts": {
            "ge_1.5": sum(v >= 1.5 for v in values),
            "ge_2.0": sum(v >= 2.0 for v in values),
            "ge_2.5": sum(v >= 2.5 for v in values),
            "ge_3.0": sum(v >= 3.0 for v in values),
        },
    }
    with SUMMARY_PATH.open("w") as f:
        json.dump(summary, f, indent=2)


def main():
    rows = load_rows()
    ensure_links(rows)
    write_labels(rows)
    write_summary(rows)
    print(
        json.dumps(
            {
                "output_dir": str(OUTPUT_DIR),
                "output_labels": str(OUTPUT_LABELS),
                "n_samples": len(rows),
                "summary_path": str(SUMMARY_PATH),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
