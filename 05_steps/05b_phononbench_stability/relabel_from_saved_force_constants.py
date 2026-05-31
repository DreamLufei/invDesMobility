#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path

import numpy as np
import phonopy
from phonopy.phonon.band_structure import get_band_qpoints_by_seekpath


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def list_force_constant_yamls(root: Path):
    return sorted(root.rglob("*.yaml"))


def classify_yaml(yaml_path: Path, imag_threshold: float):
    ph = phonopy.load(str(yaml_path))
    bands, labels, path_connections = get_band_qpoints_by_seekpath(
        ph.primitive,
        npoints=101,
        is_const_interval=True,
    )
    ph.run_band_structure(
        bands,
        path_connections=path_connections,
        labels=labels,
        is_legacy_plot=False,
    )
    band_dict = ph.get_band_structure_dict()
    all_freqs = np.concatenate(band_dict["frequencies"])
    min_frequency = float(np.min(all_freqs))
    is_stable = min_frequency >= -abs(imag_threshold)
    return {
        "structure_name": yaml_path.stem,
        "yaml_path": str(yaml_path.resolve()),
        "min_frequency": min_frequency,
        "imag_threshold": float(abs(imag_threshold)),
        "phonon_label": "Stable" if is_stable else "unStable",
        "dynamically_stable": is_stable,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Re-evaluate dynamical-stability labels from saved PhononBench force-constant YAML files."
    )
    parser.add_argument("--phonon_output_dir", required=True)
    parser.add_argument("--output_csv", required=True)
    parser.add_argument("--summary_json", required=True)
    parser.add_argument("--imag_threshold", type=float, default=0.1)
    args = parser.parse_args()

    phonon_output_dir = Path(args.phonon_output_dir)
    yaml_paths = list_force_constant_yamls(phonon_output_dir)

    rows = []
    failed = []
    for yaml_path in yaml_paths:
        try:
            rows.append(classify_yaml(yaml_path, args.imag_threshold))
        except Exception as exc:
            failed.append(
                {
                    "structure_name": yaml_path.stem,
                    "yaml_path": str(yaml_path.resolve()),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    fieldnames = [
        "structure_name",
        "yaml_path",
        "min_frequency",
        "imag_threshold",
        "phonon_label",
        "dynamically_stable",
    ]
    write_csv(Path(args.output_csv), fieldnames, rows)

    summary = {
        "phonon_output_dir": str(phonon_output_dir.resolve()),
        "imag_threshold": float(abs(args.imag_threshold)),
        "counts": {
            "yaml_total": len(yaml_paths),
            "stable_total": sum(1 for row in rows if row["dynamically_stable"]),
            "unstable_total": sum(1 for row in rows if not row["dynamically_stable"]),
            "failed_total": len(failed),
        },
        "paths": {
            "output_csv": args.output_csv,
        },
        "failed_items": failed,
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
