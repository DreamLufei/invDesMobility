#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from closed_loop_common import (  # noqa: E402
    DEFAULT_TRUST_THRESHOLDS,
    ensure_clean_dir,
    material_dirs,
    trusted_channel_rows_for_material,
    write_csv,
    write_json,
)


TRUSTED_CHANNEL_FIELDS = [
    "round_id",
    "round_index",
    "batch_id",
    "material_id",
    "channel",
    "direction",
    "carrier",
    "mobility_cm2_vs",
    "log10_mobility",
    "E1_eV",
    "C2D_J_m2",
    "E1_fit_R2",
    "C2D_fit_R2",
    "rel_e1_sigma",
    "rel_c2d_sigma",
    "min_fit_r2",
    "mass_status",
    "mass_valid_for_mobility",
    "mass_fit_R2",
    "mass_rejection_reasons",
    "mass_dynamic_band_switch",
    "n_points",
    "validation_status",
    "validation_reason",
    "trusted",
    "rejection_reasons",
    "relaxed_cif_path",
    "relaxed_contcar_path",
    "input_poscar_path",
    "workdir",
    "structure_hash",
]

TRUSTED_MATERIAL_FIELDS = [
    "round_id",
    "round_index",
    "batch_id",
    "material_id",
    "usable_channel_count",
    "best_channel",
    "best_mobility_cm2_vs",
    "best_target",
    "best_direction",
    "best_carrier",
    "relaxed_cif_path",
    "relaxed_contcar_path",
    "input_poscar_path",
    "structure_hash",
    "source_workdir",
]

REJECTED_FIELDS = [
    "round_id",
    "batch_id",
    "material_id",
    "reason",
    "failed_stages",
    "accepted_channels",
    "rejected_channels",
    "relaxed_cif_path",
    "structure_hash",
    "workdir",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract trusted closed-loop feedback from a 2d-mobility batch run.")
    parser.add_argument("--batch-root", required=True, help="Path to one completed downstream batch root.")
    parser.add_argument("--output-dir", required=True, help="Directory to write trusted feedback manifests.")
    parser.add_argument("--round-id", default="round_00_bootstrap")
    parser.add_argument("--batch-id", default="")
    parser.add_argument("--min-fit-r2", type=float, default=DEFAULT_TRUST_THRESHOLDS["min_fit_r2"])
    parser.add_argument("--max-rel-e1-sigma", type=float, default=DEFAULT_TRUST_THRESHOLDS["max_rel_e1_sigma"])
    parser.add_argument("--max-rel-c2d-sigma", type=float, default=DEFAULT_TRUST_THRESHOLDS["max_rel_c2d_sigma"])
    parser.add_argument("--min-abs-e1-ev", type=float, default=DEFAULT_TRUST_THRESHOLDS["min_abs_e1_eV"])
    parser.add_argument("--min-mass-fit-r2", type=float, default=DEFAULT_TRUST_THRESHOLDS["min_mass_fit_r2"])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    batch_root = Path(args.batch_root).resolve()
    if not batch_root.exists():
        raise SystemExit(f"missing batch root: {batch_root}")

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    trusted_cif_dir = output_dir / "trusted_relaxed_cif"
    ensure_clean_dir(trusted_cif_dir)

    thresholds = {
        "min_fit_r2": float(args.min_fit_r2),
        "max_rel_e1_sigma": float(args.max_rel_e1_sigma),
        "max_rel_c2d_sigma": float(args.max_rel_c2d_sigma),
        "min_abs_e1_eV": float(args.min_abs_e1_ev),
        "min_mass_fit_r2": float(args.min_mass_fit_r2),
    }
    round_id = str(args.round_id)
    batch_id = str(args.batch_id or batch_root.name)

    trusted_channels: list[dict[str, object]] = []
    trusted_materials: list[dict[str, object]] = []
    rejected_rows: list[dict[str, object]] = []

    for material_dir in material_dirs(batch_root):
        feedback = trusted_channel_rows_for_material(
            material_dir=material_dir,
            round_id=round_id,
            batch_id=batch_id,
            trusted_cif_dir=trusted_cif_dir,
            thresholds=thresholds,
        )
        trusted_channels.extend(feedback.trusted_channels)
        if feedback.material_row is not None:
            trusted_materials.append(feedback.material_row)
        rejected_rows.extend(feedback.rejected_rows)

    trusted_channels.sort(key=lambda row: (row["material_id"], row["channel"]))
    trusted_materials.sort(key=lambda row: row["material_id"])
    rejected_rows.sort(key=lambda row: row["material_id"])

    trusted_channels_path = output_dir / "trusted_channels.csv"
    trusted_materials_path = output_dir / "trusted_materials.csv"
    rejected_path = output_dir / "rejected_feedback.csv"
    summary_path = output_dir / "feedback_summary.json"

    write_csv(trusted_channels_path, TRUSTED_CHANNEL_FIELDS, trusted_channels)
    write_csv(trusted_materials_path, TRUSTED_MATERIAL_FIELDS, trusted_materials)
    write_csv(rejected_path, REJECTED_FIELDS, rejected_rows)

    summary = {
        "round_id": round_id,
        "batch_id": batch_id,
        "batch_root": str(batch_root),
        "thresholds": thresholds,
        "counts": {
            "materials_seen": len(material_dirs(batch_root)),
            "trusted_channel_count": len(trusted_channels),
            "trusted_material_count": len(trusted_materials),
            "rejected_material_count": len(rejected_rows),
        },
        "paths": {
            "trusted_channels_csv": str(trusted_channels_path),
            "trusted_materials_csv": str(trusted_materials_path),
            "rejected_feedback_csv": str(rejected_path),
            "trusted_relaxed_cif_dir": str(trusted_cif_dir),
        },
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
