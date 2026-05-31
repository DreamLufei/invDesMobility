#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path

import numpy as np
from pymatgen.core import Lattice, Structure
from pymatgen.io.cif import CifWriter
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer


def list_cifs(path: Path):
    return sorted(path.glob("*.cif"))


def analyze_structure(structure: Structure, symprec: float, angle_tolerance: float):
    analyzer = SpacegroupAnalyzer(
        structure,
        symprec=symprec,
        angle_tolerance=angle_tolerance,
    )
    return {
        "crystal_system": analyzer.get_crystal_system(),
        "space_group_symbol": analyzer.get_space_group_symbol(),
        "space_group_number": analyzer.get_space_group_number(),
    }


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_structure_with_strict_orthogonal_angles(structure: Structure):
    lattice = structure.lattice
    strict_lattice = Lattice.from_parameters(
        lattice.a,
        lattice.b,
        lattice.c,
        90.0,
        90.0,
        90.0,
    )
    return Structure(
        strict_lattice,
        structure.species,
        structure.frac_coords,
        coords_are_cartesian=False,
        site_properties=structure.site_properties,
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Snap near-orthorhombic CIFs to strict 90/90/90 angles while preserving "
            "lattice lengths and fractional coordinates."
        )
    )
    parser.add_argument("--input_dir", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--summary_csv", required=True)
    parser.add_argument("--summary_json", required=True)
    parser.add_argument("--target_crystal_system", default="orthorhombic")
    parser.add_argument("--max_angle_deviation_deg", type=float, default=0.6)
    parser.add_argument("--symprec", type=float, default=0.1)
    parser.add_argument("--angle_tolerance", type=float, default=5.0)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for child in output_dir.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()

    rows = []
    target_crystal_system = args.target_crystal_system.lower()

    for cif_path in list_cifs(input_dir):
        row = {
            "cif_name": cif_path.name,
            "input_cif_path": str(cif_path.resolve()),
            "output_cif_path": "",
            "target_crystal_system": target_crystal_system,
            "pre_crystal_system": "",
            "pre_space_group_symbol": "",
            "pre_space_group_number": "",
            "post_crystal_system": "",
            "post_space_group_symbol": "",
            "post_space_group_number": "",
            "a": "",
            "b": "",
            "c": "",
            "alpha_before": "",
            "beta_before": "",
            "gamma_before": "",
            "alpha_after": "",
            "beta_after": "",
            "gamma_after": "",
            "max_angle_deviation_deg": "",
            "mean_cartesian_shift_ang": "",
            "max_cartesian_shift_ang": "",
            "eligible_for_snap": False,
            "written": False,
            "error": "",
        }

        try:
            structure = Structure.from_file(cif_path)
            lattice = structure.lattice
            pre_info = analyze_structure(
                structure,
                symprec=args.symprec,
                angle_tolerance=args.angle_tolerance,
            )

            alpha_before = float(lattice.alpha)
            beta_before = float(lattice.beta)
            gamma_before = float(lattice.gamma)
            max_angle_deviation = max(
                abs(alpha_before - 90.0),
                abs(beta_before - 90.0),
                abs(gamma_before - 90.0),
            )

            row.update(
                {
                    "pre_crystal_system": pre_info["crystal_system"],
                    "pre_space_group_symbol": pre_info["space_group_symbol"],
                    "pre_space_group_number": pre_info["space_group_number"],
                    "a": float(lattice.a),
                    "b": float(lattice.b),
                    "c": float(lattice.c),
                    "alpha_before": alpha_before,
                    "beta_before": beta_before,
                    "gamma_before": gamma_before,
                    "max_angle_deviation_deg": max_angle_deviation,
                }
            )

            if pre_info["crystal_system"].lower() != target_crystal_system:
                row["error"] = (
                    f"pre_crystal_system={pre_info['crystal_system']} does not match "
                    f"target={target_crystal_system}"
                )
                rows.append(row)
                continue

            if max_angle_deviation > args.max_angle_deviation_deg:
                row["error"] = (
                    f"max_angle_deviation_deg={max_angle_deviation:.6f} exceeds "
                    f"threshold={args.max_angle_deviation_deg:.6f}"
                )
                rows.append(row)
                continue

            snapped_structure = build_structure_with_strict_orthogonal_angles(structure)
            post_info = analyze_structure(
                snapped_structure,
                symprec=args.symprec,
                angle_tolerance=args.angle_tolerance,
            )

            cartesian_shift = np.linalg.norm(
                snapped_structure.cart_coords - structure.cart_coords,
                axis=1,
            )
            output_path = output_dir / cif_path.name
            CifWriter(snapped_structure, symprec=None).write_file(str(output_path))

            row.update(
                {
                    "output_cif_path": str(output_path),
                    "post_crystal_system": post_info["crystal_system"],
                    "post_space_group_symbol": post_info["space_group_symbol"],
                    "post_space_group_number": post_info["space_group_number"],
                    "alpha_after": 90.0,
                    "beta_after": 90.0,
                    "gamma_after": 90.0,
                    "mean_cartesian_shift_ang": float(cartesian_shift.mean()) if len(cartesian_shift) else 0.0,
                    "max_cartesian_shift_ang": float(cartesian_shift.max()) if len(cartesian_shift) else 0.0,
                    "eligible_for_snap": True,
                    "written": True,
                }
            )
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"

        rows.append(row)

    summary_csv = Path(args.summary_csv)
    write_csv(
        summary_csv,
        [
            "cif_name",
            "input_cif_path",
            "output_cif_path",
            "target_crystal_system",
            "pre_crystal_system",
            "pre_space_group_symbol",
            "pre_space_group_number",
            "post_crystal_system",
            "post_space_group_symbol",
            "post_space_group_number",
            "a",
            "b",
            "c",
            "alpha_before",
            "beta_before",
            "gamma_before",
            "alpha_after",
            "beta_after",
            "gamma_after",
            "max_angle_deviation_deg",
            "mean_cartesian_shift_ang",
            "max_cartesian_shift_ang",
            "eligible_for_snap",
            "written",
            "error",
        ],
        rows,
    )

    written_rows = [row for row in rows if row["written"]]
    summary = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "target_crystal_system": target_crystal_system,
        "max_angle_deviation_deg": args.max_angle_deviation_deg,
        "symprec": args.symprec,
        "angle_tolerance": args.angle_tolerance,
        "counts": {
            "input_cif_total": len(rows),
            "written_cif_total": len(written_rows),
            "skipped_or_failed_total": len(rows) - len(written_rows),
        },
        "max_observed_angle_deviation_deg": max(
            (row["max_angle_deviation_deg"] for row in rows if row["max_angle_deviation_deg"] != ""),
            default=0.0,
        ),
        "max_written_cartesian_shift_ang": max(
            (row["max_cartesian_shift_ang"] for row in written_rows),
            default=0.0,
        ),
        "paths": {
            "summary_csv": str(summary_csv),
            "output_dir": str(output_dir),
        },
    }

    summary_json = Path(args.summary_json)
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
