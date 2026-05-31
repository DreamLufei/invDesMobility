#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(ROOT_DIR / "00_project"))
sys.path.insert(0, str(SCRIPT_DIR))

from paths import DIFFCSP_ROOT, INV_DES_FLOW_ROOT, SOURCE_CIF_DIR  # noqa: E402
from closed_loop_common import (  # noqa: E402
    build_relaxed_structure,
    collect_feedback_rows,
    diffcsp_material_row,
    structure_hash,
    write_diffcsp_csv,
    write_json,
)


def _write_diffcsp_data_config(*, dataset_name: str, dataset_dir: Path) -> Path:
    conf_data_dir = (DIFFCSP_ROOT / "conf" / "data").resolve()
    conf_data_dir.mkdir(parents=True, exist_ok=True)
    template_path = conf_data_dir / "mobility2d_highquality280.yaml"
    config_path = conf_data_dir / f"{dataset_name}.yaml"

    template = template_path.read_text(encoding="utf-8")
    rewritten_lines: list[str] = []
    replaced_root = False
    for line in template.splitlines():
        if line.startswith("root_path:"):
            rewritten_lines.append(f"root_path: {dataset_dir}")
            replaced_root = True
        else:
            rewritten_lines.append(line)
    if not replaced_root:
        raise SystemExit(f"failed to locate root_path in template config: {template_path}")
    config_path.write_text("\n".join(rewritten_lines) + "\n", encoding="utf-8")
    return config_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a weighted DiffCSP round dataset from trusted relaxed structures.")
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--manifest-path", required=True)
    parser.add_argument("--base-cif-dir", default=str(SOURCE_CIF_DIR))
    parser.add_argument("--feedback-csv", action="append", default=[])
    parser.add_argument("--feedback-weight", type=int, default=12)
    parser.add_argument("--min-train-rows", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def _set_indices(rows: list[list[object]]) -> list[list[object]]:
    normalized: list[list[object]] = []
    for idx, row in enumerate(rows):
        cloned = list(row)
        cloned[0] = idx
        cloned[1] = idx
        normalized.append(cloned)
    return normalized


def main() -> int:
    args = build_parser().parse_args()
    dataset_dir = (INV_DES_FLOW_ROOT / "data" / args.dataset_name).resolve()
    dataset_dir.mkdir(parents=True, exist_ok=True)

    for child in dataset_dir.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()

    unique_records: dict[str, dict[str, object]] = {}

    base_cif_dir = Path(args.base_cif_dir).resolve()
    for cif_path in sorted(base_cif_dir.glob("*.cif")):
        structure = build_relaxed_structure(cif_path)
        digest = structure_hash(structure)
        unique_records[digest] = {
            "source": "base",
            "material_id": cif_path.name,
            "structure": structure,
            "weight": 1,
            "round_id": "base",
        }

    feedback_rows = collect_feedback_rows(Path(item).resolve() for item in args.feedback_csv)
    for row in feedback_rows:
        cif_path = Path(str(row.get("relaxed_cif_path") or "")).resolve()
        if not cif_path.exists():
            continue
        structure = build_relaxed_structure(cif_path)
        digest = str(row.get("structure_hash") or "") or structure_hash(structure)
        unique_records[digest] = {
            "source": "feedback",
            "material_id": f"{row.get('round_id', 'feedback')}__{row.get('material_id', cif_path.stem)}.cif",
            "structure": structure,
            "weight": int(args.feedback_weight),
            "round_id": row.get("round_id", ""),
        }

    ordered_records = sorted(unique_records.values(), key=lambda item: (str(item.get("source")), str(item.get("material_id"))))
    data_rows = [
        diffcsp_material_row(idx=idx, material_id=str(record["material_id"]), structure=record["structure"])
        for idx, record in enumerate(ordered_records)
    ]

    weighted_train_rows: list[list[object]] = []
    for idx, record in enumerate(ordered_records):
        base_row = diffcsp_material_row(idx=idx, material_id=str(record["material_id"]), structure=record["structure"])
        weighted_train_rows.extend([list(base_row) for _ in range(int(record["weight"]))])

    if not weighted_train_rows:
        raise SystemExit("no structures available to build DiffCSP dataset")

    repeat_times = max(1, math.ceil(int(args.min_train_rows) / len(weighted_train_rows)))
    train_rows = weighted_train_rows * repeat_times

    rng = random.Random(int(args.seed))
    val_rows = [list(row) for row in data_rows]
    test_rows = [list(row) for row in data_rows]
    rng.shuffle(train_rows)
    rng.shuffle(val_rows)
    rng.shuffle(test_rows)

    write_diffcsp_csv(dataset_dir / "data_materials.csv", _set_indices([list(row) for row in data_rows]))
    write_diffcsp_csv(dataset_dir / "train.csv", _set_indices(train_rows))
    write_diffcsp_csv(dataset_dir / "val.csv", _set_indices(val_rows))
    write_diffcsp_csv(dataset_dir / "test.csv", _set_indices(test_rows))
    data_config_path = _write_diffcsp_data_config(dataset_name=args.dataset_name, dataset_dir=dataset_dir)

    summary = {
        "dataset_name": args.dataset_name,
        "dataset_dir": str(dataset_dir),
        "base_cif_dir": str(base_cif_dir),
        "feedback_csvs": [str(Path(item).resolve()) for item in args.feedback_csv],
        "feedback_weight": int(args.feedback_weight),
        "min_train_rows": int(args.min_train_rows),
        "counts": {
            "unique_structures": len(data_rows),
            "feedback_unique_structures": sum(1 for item in ordered_records if item["source"] == "feedback"),
            "weighted_train_rows_before_repeat": len(weighted_train_rows),
            "train_rows": len(train_rows),
            "val_rows": len(val_rows),
            "test_rows": len(test_rows),
        },
        "paths": {
            "data_materials_csv": str(dataset_dir / "data_materials.csv"),
            "train_csv": str(dataset_dir / "train.csv"),
            "val_csv": str(dataset_dir / "val.csv"),
            "test_csv": str(dataset_dir / "test.csv"),
            "hydra_data_config": str(data_config_path),
        },
    }
    write_json(Path(args.manifest_path), summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
