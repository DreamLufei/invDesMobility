#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(ROOT_DIR / "00_project"))
sys.path.insert(0, str(SCRIPT_DIR))

from paths import SOURCE_CIF_DIR  # noqa: E402
from closed_loop_common import collect_feedback_rows, load_id_prop_rows, write_json  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a round-specific ALIGNN mobility dataset from trusted feedback.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest-path", required=True)
    parser.add_argument("--base-cif-dir", default=str(SOURCE_CIF_DIR))
    parser.add_argument("--base-labels", default=str(Path(SOURCE_CIF_DIR) / "id_prop.csv"))
    parser.add_argument("--feedback-csv", action="append", default=[])
    return parser


def _copy_or_link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    os.symlink(src.resolve(), dst)


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for child in output_dir.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()

    base_cif_dir = Path(args.base_cif_dir).resolve()
    base_labels = Path(args.base_labels).resolve()
    feedback_paths = [Path(item).resolve() for item in args.feedback_csv]
    feedback_rows = collect_feedback_rows(feedback_paths)

    label_rows: list[tuple[str, float]] = []
    manifest_rows: list[dict[str, object]] = []

    for filename, target in load_id_prop_rows(base_labels):
        src = base_cif_dir / filename
        if not src.exists():
            continue
        _copy_or_link(src, output_dir / filename)
        label_rows.append((filename, float(target)))
        manifest_rows.append(
            {
                "dataset_source": "base",
                "filename": filename,
                "target": float(target),
                "round_id": "base",
                "material_id": Path(filename).stem,
                "best_channel": "",
                "best_mobility_cm2_vs": "",
                "structure_hash": "",
            }
        )

    dedup_by_hash: dict[str, dict[str, str]] = {}
    for row in feedback_rows:
        structure_hash = str(row.get("structure_hash") or "").strip()
        if not structure_hash:
            structure_hash = str(row.get("material_id") or "")
        current = dedup_by_hash.get(structure_hash)
        current_round = int(current.get("round_index") or 0) if current else -1
        next_round = int(row.get("round_index") or 0)
        if current is None or next_round >= current_round:
            dedup_by_hash[structure_hash] = row

    for row in sorted(dedup_by_hash.values(), key=lambda item: (int(item.get("round_index") or 0), item.get("material_id") or "")):
        src = Path(str(row["relaxed_cif_path"])).resolve()
        if not src.exists():
            continue
        filename = f"{row['round_id']}__{row['material_id']}.cif"
        _copy_or_link(src, output_dir / filename)
        target = float(row["best_target"])
        label_rows.append((filename, target))
        manifest_rows.append(
            {
                "dataset_source": "feedback",
                "filename": filename,
                "target": target,
                "round_id": row.get("round_id", ""),
                "round_index": int(row.get("round_index") or 0),
                "material_id": row.get("material_id", ""),
                "best_channel": row.get("best_channel", ""),
                "best_mobility_cm2_vs": row.get("best_mobility_cm2_vs", ""),
                "structure_hash": row.get("structure_hash", ""),
            }
        )

    id_prop_path = output_dir / "id_prop.csv"
    with id_prop_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        for filename, target in label_rows:
            writer.writerow([filename, f"{target:.6f}"])

    manifest_csv = output_dir / "dataset_manifest.csv"
    with manifest_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "dataset_source",
            "filename",
            "target",
            "round_id",
            "round_index",
            "material_id",
            "best_channel",
            "best_mobility_cm2_vs",
            "structure_hash",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    summary = {
        "output_dir": str(output_dir),
        "base_cif_dir": str(base_cif_dir),
        "base_labels": str(base_labels),
        "feedback_csvs": [str(path) for path in feedback_paths],
        "counts": {
            "base_samples": sum(1 for row in manifest_rows if row["dataset_source"] == "base"),
            "feedback_samples": sum(1 for row in manifest_rows if row["dataset_source"] == "feedback"),
            "total_samples": len(label_rows),
        },
        "paths": {
            "id_prop_csv": str(id_prop_path),
            "dataset_manifest_csv": str(manifest_csv),
        },
    }
    write_json(Path(args.manifest_path), summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
