#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

from pymatgen.core import Structure

try:
    from pymongo import MongoClient, UpdateOne
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"pymongo is required for Mongo publishing: {exc}") from exc


ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "00_project"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish strict90 surviving candidates into the active mobility Mongo collection.")
    parser.add_argument("--strict90-csv", required=True)
    parser.add_argument("--output-manifest", required=True)
    parser.add_argument("--mongo-uri", default=os.environ.get("MONGO_URI", ""))
    parser.add_argument("--mongo-db", default=os.environ.get("MONGO_DB", "materials_database"))
    parser.add_argument("--mongo-collection", default=os.environ.get("MONGO_COLLECTION", "Vertical_NM_Sample_20"))
    parser.add_argument("--round-index", type=int, required=True)
    parser.add_argument("--round-id", required=True)
    parser.add_argument("--parent-round-id", required=True)
    parser.add_argument("--generator-model-id", required=True)
    parser.add_argument("--alignn-model-id", required=True)
    parser.add_argument("--feedback-snapshot-id", required=True)
    parser.add_argument("--pipeline-run-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_material_id(round_id: str, strict90_cif_path: str) -> str:
    return f"{round_id}__{Path(strict90_cif_path).stem}"


def build_source_key(*, pipeline_run_id: str, candidate_rank: int, source_candidate_name: str) -> str:
    return f"{pipeline_run_id}::rank_{int(candidate_rank):02d}::{Path(source_candidate_name).name}"


def main() -> int:
    args = build_parser().parse_args()
    if not args.mongo_uri:
        raise SystemExit("missing --mongo-uri or MONGO_URI")

    rows = read_rows(Path(args.strict90_csv).resolve())
    surviving_rows = [
        row
        for row in rows
        if truthy(row.get("strict90_written")) and str(row.get("strict90_cif_path") or "").strip()
    ]

    ops: list[UpdateOne] = []
    published_preview: list[dict[str, object]] = []
    for idx, row in enumerate(surviving_rows, start=1):
        strict90_cif_path = Path(str(row["strict90_cif_path"])).resolve()
        if not strict90_cif_path.exists():
            continue
        structure = Structure.from_file(str(strict90_cif_path))
        material_id = build_material_id(args.round_id, str(strict90_cif_path))
        candidate_rank = int(row.get("rank") or idx)
        source_candidate_name = str(row.get("cif_name") or Path(row.get("cif_path") or "").name)
        source_key = build_source_key(
            pipeline_run_id=str(args.pipeline_run_id),
            candidate_rank=candidate_rank,
            source_candidate_name=source_candidate_name,
        )
        loop_metadata = {
            "round_index": int(args.round_index),
            "round_id": str(args.round_id),
            "parent_round_id": str(args.parent_round_id),
            "generator_model_id": str(args.generator_model_id),
            "alignn_model_id": str(args.alignn_model_id),
            "feedback_snapshot_id": str(args.feedback_snapshot_id),
            "pipeline_run_id": str(args.pipeline_run_id),
            "source_candidate_name": source_candidate_name,
            "submit_count_in_round": idx,
            "candidate_rank": candidate_rank,
        }
        screening = {
            "bandgap": row.get("bandgap", ""),
            "mobility_score": row.get("mobility_score", ""),
            "strict90_cif_path": str(strict90_cif_path),
            "strict90_max_angle_deviation_deg": row.get("strict90_max_angle_deviation_deg", ""),
            "strict90_max_cartesian_shift_ang": row.get("strict90_max_cartesian_shift_ang", ""),
            "original_cif_path": row.get("cif_path", ""),
            "published_at": utc_iso_now(),
        }
        update_doc = {
            "source_key": source_key,
            "material_id": material_id,
            "structure": structure.as_dict(),
            "invdes_source": {
                "run_id": str(args.pipeline_run_id),
                "round_id": str(args.round_id),
                "source_candidate_name": source_candidate_name,
                "candidate_rank": candidate_rank,
            },
            "loop_metadata": loop_metadata,
            "invdes_screening": screening,
        }
        ops.append(UpdateOne({"material_id": material_id}, {"$set": update_doc}, upsert=True))
        published_preview.append({
            "source_key": source_key,
            "material_id": material_id,
            "source_candidate_name": source_candidate_name,
            "submit_count_in_round": idx,
        })

    summary = {
        "mongo_db": args.mongo_db,
        "mongo_collection": args.mongo_collection,
        "strict90_csv": str(Path(args.strict90_csv).resolve()),
        "round_id": args.round_id,
        "round_index": int(args.round_index),
        "counts": {
            "strict90_rows": len(rows),
            "surviving_rows": len(surviving_rows),
            "publishable_rows": len(ops),
        },
        "published_preview": published_preview,
        "dry_run": bool(args.dry_run),
    }

    if not args.dry_run and ops:
        client = MongoClient(args.mongo_uri)
        try:
            collection = client[args.mongo_db][args.mongo_collection]
            collection.create_index("material_id", unique=True, name="uniq_material_id")
            result = collection.bulk_write(ops, ordered=True)
            summary["mongo_write_result"] = {
                "matched_count": int(result.matched_count),
                "modified_count": int(result.modified_count),
                "upserted_count": int(result.upserted_count),
            }
        finally:
            client.close()

    manifest_path = Path(args.output_manifest).resolve()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
