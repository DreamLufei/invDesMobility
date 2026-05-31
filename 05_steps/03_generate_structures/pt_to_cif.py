#!/usr/bin/env python
import argparse
import traceback
from pathlib import Path
import sys

import torch
from pymatgen.core import Lattice, Structure
from pymatgen.io.cif import CifWriter

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "00_project"))

from paths import DEFAULT_GENERATION_CIF_DIR, DEFAULT_GENERATION_PT_DIR, LOGS_ROOT  # noqa: E402


def iter_samples(data):
    frac_coords = data["frac_coords"]
    atom_types = data["atom_types"]
    num_atoms = data["num_atoms"]
    lengths = data["lengths"]
    angles = data["angles"]

    start = 0
    for index, atom_count in enumerate(num_atoms.tolist()):
        end = start + atom_count
        yield {
            "sample_index": index,
            "frac_coords": frac_coords[start:end],
            "atom_types": atom_types[start:end],
            "lengths": lengths[index],
            "angles": angles[index],
        }
        start = end


def build_structure(sample):
    atom_types = sample["atom_types"]
    if atom_types.ndim > 1:
        atom_types = atom_types.argmax(dim=-1) + 1

    atomic_numbers = [int(value) for value in atom_types.tolist()]
    if any(number <= 0 or number > 118 for number in atomic_numbers):
        raise ValueError(f"invalid atomic numbers: {atomic_numbers}")

    lattice = Lattice.from_parameters(
        *sample["lengths"].tolist(),
        *sample["angles"].tolist(),
    )
    return Structure(
        lattice=lattice,
        species=atomic_numbers,
        coords=sample["frac_coords"].tolist(),
        coords_are_cartesian=False,
        to_unit_cell=True,
        validate_proximity=False,
    )


def main():
    parser = argparse.ArgumentParser(description="Convert DiffCSP generated pt files to CIF.")
    parser.add_argument(
        "--input_dir",
        default=str(DEFAULT_GENERATION_PT_DIR),
    )
    parser.add_argument(
        "--output_dir",
        default=str(DEFAULT_GENERATION_CIF_DIR),
    )
    parser.add_argument(
        "--log_path",
        default=str(LOGS_ROOT / "03_generate_structures" / "pt_to_cif_bad_samples.log"),
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    log_path = Path(args.log_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    pt_files = sorted(input_dir.glob("*.pt"))
    if not pt_files:
        raise SystemExit(f"No pt files found in {input_dir}")

    converted = 0
    skipped = 0
    with log_path.open("a") as log_file:
        for pt_path in pt_files:
            try:
                data = torch.load(pt_path, map_location="cpu")
            except Exception:
                skipped += 1
                log_file.write(f"[LOAD_FAIL] {pt_path}\n{traceback.format_exc()}\n")
                continue

            for sample in iter_samples(data):
                stem = f"{pt_path.stem}__sample_{sample['sample_index']:04d}"
                cif_path = output_dir / f"{stem}.cif"
                try:
                    structure = build_structure(sample)
                    CifWriter(structure).write_file(cif_path)
                    converted += 1
                except Exception:
                    skipped += 1
                    log_file.write(f"[SAMPLE_FAIL] {pt_path} {stem}\n{traceback.format_exc()}\n")

    print(
        {
            "input_dir": str(input_dir),
            "output_dir": str(output_dir),
            "converted": converted,
            "skipped": skipped,
            "log_path": str(log_path),
        }
    )


if __name__ == "__main__":
    main()
