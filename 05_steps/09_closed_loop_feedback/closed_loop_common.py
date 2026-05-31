#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from pymatgen.core import Structure
from pymatgen.io.cif import CifWriter


DEFAULT_TRUST_THRESHOLDS: dict[str, float] = {
    "min_fit_r2": 0.90,
    "max_rel_e1_sigma": 0.50,
    "max_rel_c2d_sigma": 0.20,
    "min_abs_e1_eV": 0.05,
    "min_mass_fit_r2": 0.95,
}

DIFFCSP_HEADER = [
    "",
    "Unnamed: 0",
    "material_id",
    "formation_energy_per_atom",
    "band_gap",
    "pretty_formula",
    "e_above_hull",
    "elements",
    "cif",
    "spacegroup.number",
    "spacegroup.number.conv",
    "cif.conv",
]


@dataclass(frozen=True)
class TrustedChannelRecord:
    row: dict[str, Any]
    trusted: bool


@dataclass(frozen=True)
class MaterialFeedback:
    material_row: dict[str, Any] | None
    trusted_channels: list[dict[str, Any]]
    rejected_rows: list[dict[str, Any]]


def safe_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except Exception:
        return None


def safe_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(value)
    except Exception:
        return None


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def ensure_clean_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def canonical_subchannel(direction: str, carrier: str) -> str:
    return f"{carrier}_{direction}"


def round_index_from_id(round_id: str) -> int | None:
    text = str(round_id)
    match = re.search(r"(?:round_|loop_)(\d+)", text)
    if match:
        try:
            return int(match.group(1))
        except Exception:
            return None
    match = re.search(r"(\d+)$", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def material_dirs(batch_root: Path) -> list[Path]:
    return sorted(
        path
        for path in batch_root.iterdir()
        if path.is_dir() and (path / "mobility_calculation").exists()
    )


def compute_rel_sigma(value: float | None, sigma: float | None) -> float | None:
    if value is None or sigma is None:
        return None
    if abs(value) < 1e-12:
        return None
    return abs(sigma / value)


def structure_hash(structure: Structure) -> str:
    lattice = [[round(float(item), 6) for item in row] for row in structure.lattice.matrix]
    sites = []
    for site in structure.sites:
        frac = [round(float(item) % 1.0, 6) for item in site.frac_coords]
        sites.append({"species": site.species_string, "frac_coords": frac})
    sites.sort(key=lambda item: (item["species"], item["frac_coords"]))
    payload = {
        "lattice": lattice,
        "sites": sites,
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def export_structure_to_cif(structure: Structure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = CifWriter(structure)
    path.write_text(str(writer), encoding="utf-8")


def build_relaxed_structure(contcar_path: Path) -> Structure:
    return Structure.from_file(str(contcar_path))


def diffcsp_material_row(*, idx: int, material_id: str, structure: Structure) -> list[Any]:
    cif_text = str(CifWriter(structure))
    return [
        idx,
        idx,
        material_id,
        0,
        0,
        structure.composition.reduced_formula,
        0,
        str([str(element) for element in structure.elements]),
        cif_text,
        0,
        0,
        cif_text,
    ]


def write_diffcsp_csv(path: Path, rows: list[list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(DIFFCSP_HEADER)
        writer.writerows(rows)


def trusted_channel_rows_for_material(
    *,
    material_dir: Path,
    round_id: str,
    batch_id: str,
    trusted_cif_dir: Path,
    thresholds: dict[str, float],
) -> MaterialFeedback:
    material_id = material_dir.name
    workdir = material_dir / "mobility_calculation"
    outcome_path = workdir / "material_outcome.json"
    results_path = workdir / "mobility_results.json"
    relax_contcar = workdir / "01_relax" / "CONTCAR"
    input_poscar = material_dir / "POSCAR"

    rejected_rows: list[dict[str, Any]] = []
    trusted_rows: list[dict[str, Any]] = []

    if not outcome_path.exists():
        rejected_rows.append(
            {
                "round_id": round_id,
                "batch_id": batch_id,
                "material_id": material_id,
                "reason": "missing_material_outcome",
                "workdir": str(workdir),
            }
        )
        return MaterialFeedback(material_row=None, trusted_channels=[], rejected_rows=rejected_rows)

    if not results_path.exists():
        rejected_rows.append(
            {
                "round_id": round_id,
                "batch_id": batch_id,
                "material_id": material_id,
                "reason": "missing_mobility_results",
                "workdir": str(workdir),
            }
        )
        return MaterialFeedback(material_row=None, trusted_channels=[], rejected_rows=rejected_rows)

    if not relax_contcar.exists():
        rejected_rows.append(
            {
                "round_id": round_id,
                "batch_id": batch_id,
                "material_id": material_id,
                "reason": "missing_relaxed_structure",
                "workdir": str(workdir),
            }
        )
        return MaterialFeedback(material_row=None, trusted_channels=[], rejected_rows=rejected_rows)

    outcome = load_json(outcome_path)
    results = load_json(results_path)
    validation = dict(outcome.get("validation_report", {}) or {})
    stage_status = dict(outcome.get("stage_status", {}) or {})
    required_stages = ["prepare", "relax", "scf", "band", "effective_mass", "strain_loop", "mobility"]
    failed_stages = [stage for stage in required_stages if str(stage_status.get(stage) or "") != "success"]
    completed = str(outcome.get("status") or "") == "completed" and str(outcome.get("final_status") or "") == "completed"
    if not completed or failed_stages:
        rejected_rows.append(
            {
                "round_id": round_id,
                "batch_id": batch_id,
                "material_id": material_id,
                "reason": "task_not_completed",
                "failed_stages": ",".join(failed_stages),
                "workdir": str(workdir),
            }
        )
        return MaterialFeedback(material_row=None, trusted_channels=[], rejected_rows=rejected_rows)

    relaxed_structure = build_relaxed_structure(relax_contcar)
    relaxed_cif_path = trusted_cif_dir / f"{material_id}.cif"
    export_structure_to_cif(relaxed_structure, relaxed_cif_path)
    structure_digest = structure_hash(relaxed_structure)

    results_by_direction = dict(results.get("results_by_direction", {}) or {})
    channel_reviews = dict(validation.get("channel_reviews", {}) or {})

    for direction, direction_payload in sorted(results_by_direction.items()):
        direction_payload = dict(direction_payload or {})
        for carrier in ("electron", "hole"):
            channel_payload = dict(direction_payload.get(carrier, {}) or {})
            channel_name = canonical_subchannel(direction, carrier)
            review = dict(channel_reviews.get(channel_name, {}) or {})
            mobility_cm2_vs = safe_float(channel_payload.get("mobility_cm2_Vs"))
            e1_ev = safe_float(channel_payload.get("E1_eV"))
            c2d_j_m2 = safe_float(channel_payload.get("C2D_J_m2"))
            e1_fit_r2 = safe_float(channel_payload.get("E1_fit_R2"))
            c2d_fit_r2 = safe_float(channel_payload.get("C2D_fit_R2"))
            e1_sigma = safe_float(channel_payload.get("E1_eV_sigma"))
            c2d_sigma = safe_float(channel_payload.get("C2D_sigma_J_m2"))
            rel_e1_sigma = safe_float(review.get("rel_e1_sigma"))
            rel_c2d_sigma = safe_float(review.get("rel_c2d_sigma"))
            if rel_e1_sigma is None:
                rel_e1_sigma = compute_rel_sigma(e1_ev, e1_sigma)
            if rel_c2d_sigma is None:
                rel_c2d_sigma = compute_rel_sigma(c2d_j_m2, c2d_sigma)
            mass_status = str(channel_payload.get("mass_status") or review.get("mass_status") or "").strip()
            mass_valid_for_mobility = channel_payload.get("mass_valid_for_mobility")
            if isinstance(mass_valid_for_mobility, str):
                mass_valid_for_mobility = truthy(mass_valid_for_mobility)
            mass_fit_r2 = safe_float(channel_payload.get("mass_fit_R2") or review.get("mass_fit_R2"))
            mass_dynamic_band_switch = channel_payload.get("mass_dynamic_band_switch", review.get("mass_dynamic_band_switch"))
            mass_rejection_reasons = channel_payload.get("mass_rejection_reasons") or review.get("mass_rejection_reasons") or []
            if isinstance(mass_rejection_reasons, str):
                mass_rejection_reasons = [item for item in mass_rejection_reasons.split(",") if item]
            min_fit_r2 = None
            if e1_fit_r2 is not None and c2d_fit_r2 is not None:
                min_fit_r2 = min(e1_fit_r2, c2d_fit_r2)

            conditions = {
                "mobility_positive": mobility_cm2_vs is not None and mobility_cm2_vs > 0,
                "e1_numeric": e1_ev is not None,
                "c2d_numeric": c2d_j_m2 is not None,
                "e1_fit_numeric": e1_fit_r2 is not None,
                "c2d_fit_numeric": c2d_fit_r2 is not None,
                "fit_r2": min_fit_r2 is not None and min_fit_r2 >= thresholds["min_fit_r2"],
                "rel_e1_sigma": rel_e1_sigma is not None and rel_e1_sigma <= thresholds["max_rel_e1_sigma"],
                "rel_c2d_sigma": rel_c2d_sigma is not None and rel_c2d_sigma <= thresholds["max_rel_c2d_sigma"],
                "abs_e1": e1_ev is not None and abs(e1_ev) >= thresholds["min_abs_e1_eV"],
                "mass_status": mass_status in {"", "accepted"} and mass_valid_for_mobility is not False,
                "mass_fit_r2": mass_fit_r2 is None or mass_fit_r2 >= thresholds.get("min_mass_fit_r2", 0.95),
                "mass_no_band_switch": mass_dynamic_band_switch is not True,
            }
            trusted = all(conditions.values())
            rejection_reasons = [name for name, ok in conditions.items() if not ok]
            rejection_reasons.extend(str(item) for item in mass_rejection_reasons)
            row = {
                "round_id": round_id,
                "round_index": round_index_from_id(round_id),
                "batch_id": batch_id,
                "material_id": material_id,
                "channel": channel_name,
                "direction": direction,
                "carrier": carrier,
                "mobility_cm2_vs": mobility_cm2_vs,
                "log10_mobility": math.log10(mobility_cm2_vs) if mobility_cm2_vs and mobility_cm2_vs > 0 else None,
                "E1_eV": e1_ev,
                "C2D_J_m2": c2d_j_m2,
                "E1_fit_R2": e1_fit_r2,
                "C2D_fit_R2": c2d_fit_r2,
                "rel_e1_sigma": rel_e1_sigma,
                "rel_c2d_sigma": rel_c2d_sigma,
                "min_fit_r2": min_fit_r2,
                "mass_status": mass_status,
                "mass_valid_for_mobility": mass_valid_for_mobility,
                "mass_fit_R2": mass_fit_r2,
                "mass_rejection_reasons": ",".join(str(item) for item in mass_rejection_reasons),
                "mass_dynamic_band_switch": mass_dynamic_band_switch,
                "n_points": safe_int(direction_payload.get("n_points")),
                "validation_status": review.get("status", ""),
                "validation_reason": review.get("reason", ""),
                "trusted": trusted,
                "rejection_reasons": ",".join(rejection_reasons),
                "relaxed_cif_path": str(relaxed_cif_path),
                "relaxed_contcar_path": str(relax_contcar),
                "input_poscar_path": str(input_poscar),
                "workdir": str(workdir),
                "structure_hash": structure_digest,
            }
            if trusted:
                trusted_rows.append(row)

    if not trusted_rows:
        rejected_rows.append(
            {
                "round_id": round_id,
                "batch_id": batch_id,
                "material_id": material_id,
                "reason": "no_trusted_channels",
                "accepted_channels": ",".join(list(outcome.get("accepted_channels", []) or [])),
                "rejected_channels": ",".join(list(outcome.get("rejected_channels", []) or [])),
                "workdir": str(workdir),
                "relaxed_cif_path": str(relaxed_cif_path),
                "structure_hash": structure_digest,
            }
        )
        return MaterialFeedback(material_row=None, trusted_channels=[], rejected_rows=rejected_rows)

    best_row = max(trusted_rows, key=lambda item: float(item["mobility_cm2_vs"] or -1.0))
    material_row = {
        "round_id": round_id,
        "round_index": round_index_from_id(round_id),
        "batch_id": batch_id,
        "material_id": material_id,
        "usable_channel_count": len(trusted_rows),
        "best_channel": best_row["channel"],
        "best_mobility_cm2_vs": best_row["mobility_cm2_vs"],
        "best_target": best_row["log10_mobility"],
        "best_direction": best_row["direction"],
        "best_carrier": best_row["carrier"],
        "relaxed_cif_path": best_row["relaxed_cif_path"],
        "relaxed_contcar_path": best_row["relaxed_contcar_path"],
        "input_poscar_path": best_row["input_poscar_path"],
        "structure_hash": structure_digest,
        "source_workdir": str(workdir),
    }
    return MaterialFeedback(material_row=material_row, trusted_channels=trusted_rows, rejected_rows=rejected_rows)


def load_id_prop_rows(path: Path) -> list[tuple[str, float]]:
    rows: list[list[str]] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    if rows and len(rows[0]) >= 2 and rows[0][0].strip().lower() == "filename":
        rows = rows[1:]
    parsed: list[tuple[str, float]] = []
    for row in rows:
        if len(row) < 2:
            continue
        try:
            parsed.append((row[0].strip(), float(row[1])))
        except Exception:
            continue
    return parsed


def collect_feedback_rows(paths: Iterable[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        if path.exists():
            rows.extend(read_csv_rows(path))
    return rows
