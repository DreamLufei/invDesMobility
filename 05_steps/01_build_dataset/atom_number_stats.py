#!/usr/bin/env python
import argparse
import json
from collections import Counter
from pathlib import Path
import sys

from pymatgen.core import Structure

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "00_project"))

from paths import METADATA_DIR, SOURCE_CIF_DIR  # noqa: E402


def build_num_atoms_distribution(counter, total_structures):
    max_atoms = max(counter) if counter else 0
    distribution = [0.0] * (max_atoms + 1)
    for num_atoms, count in counter.items():
        distribution[num_atoms] = count / total_structures
    return distribution


def main():
    parser = argparse.ArgumentParser(description="Compute atom-count statistics for DiffCSP generation.")
    parser.add_argument(
        "--cif_dir",
        default=str(SOURCE_CIF_DIR),
    )
    parser.add_argument(
        "--output_json",
        default=str(METADATA_DIR / "mobility2d_highquality280_atomic_dist.json"),
    )
    args = parser.parse_args()

    cif_dir = Path(args.cif_dir)
    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    cif_files = sorted(cif_dir.glob("*.cif"))
    if not cif_files:
        raise SystemExit(f"No CIF files found in {cif_dir}")

    num_atoms_counter = Counter()
    atomic_number_counter = Counter()
    failures = []

    for cif_path in cif_files:
        try:
            structure = Structure.from_file(cif_path)
            num_atoms = len(structure)
            num_atoms_counter[num_atoms] += 1
            for atomic_number in structure.atomic_numbers:
                atomic_number_counter[int(atomic_number)] += 1
        except Exception as exc:
            failures.append({"cif": str(cif_path), "error": str(exc)})

    total_structures = sum(num_atoms_counter.values())
    num_atoms_distribution = build_num_atoms_distribution(
        num_atoms_counter, total_structures
    )
    total_atoms = sum(atomic_number_counter.values())
    atomic_number_distribution = {
        str(atomic_number): count / total_atoms
        for atomic_number, count in sorted(atomic_number_counter.items())
    }

    payload = {
        "dataset_name": "mobility2d_highquality280",
        "cif_dir": str(cif_dir),
        "num_structures": total_structures,
        "num_atoms_counter": dict(sorted(num_atoms_counter.items())),
        "num_atoms_distribution": num_atoms_distribution,
        "max_atoms_per_structure": max(num_atoms_counter) if num_atoms_counter else 0,
        "total_atoms": total_atoms,
        "atomic_number_counter": {
            str(key): value for key, value in sorted(atomic_number_counter.items())
        },
        "atomic_number_distribution": atomic_number_distribution,
        "failures": failures,
    }
    output_json.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
