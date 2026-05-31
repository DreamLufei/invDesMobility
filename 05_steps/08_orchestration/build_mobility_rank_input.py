#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def safe_float(value: object) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge bandgap, formation, and phonon-stability outputs into a mobility-ranking input CSV."
    )
    parser.add_argument("--bandgap-csv", required=True)
    parser.add_argument("--formation-selected-csv", required=True)
    parser.add_argument("--phonon-stable-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    args = parser.parse_args()

    bandgap_rows = read_rows(Path(args.bandgap_csv))
    formation_rows = read_rows(Path(args.formation_selected_csv))
    phonon_rows = read_rows(Path(args.phonon_stable_csv))

    bandgap_by_name = {str(row.get("cif_name") or "").strip(): row for row in bandgap_rows}
    formation_by_name = {str(row.get("cif_name") or "").strip(): row for row in formation_rows}

    merged_rows: list[dict[str, object]] = []
    missing_bandgap = 0
    missing_formation = 0
    for row in phonon_rows:
        cif_name = str(row.get("cif_name") or "").strip()
        bandgap_row = bandgap_by_name.get(cif_name)
        formation_row = formation_by_name.get(cif_name)
        if bandgap_row is None:
            missing_bandgap += 1
        if formation_row is None:
            missing_formation += 1
        exported_cif_path = str(row.get("exported_cif_path") or "").strip()
        merged_rows.append(
            {
                "cif_name": cif_name,
                "cif_path": exported_cif_path,
                "source_cif_path": row.get("source_cif_path", ""),
                "relaxed_cif_path": row.get("relaxed_cif_path", ""),
                "bandgap": bandgap_row.get("bandgap", "") if bandgap_row else "",
                "bandgap_numeric": safe_float(bandgap_row.get("bandgap")) if bandgap_row else None,
                "is_nonmetal": bandgap_row.get("is_nonmetal", "") if bandgap_row else "",
                "formation_energy": formation_row.get("formation_energy", "") if formation_row else "",
                "passes_formation_filter": formation_row.get("passes_formation_filter", "") if formation_row else "",
                "phonon_label": row.get("phonon_label", ""),
                "dynamically_stable": row.get("dynamically_stable", ""),
            }
        )

    fieldnames = [
        "cif_name",
        "cif_path",
        "source_cif_path",
        "relaxed_cif_path",
        "bandgap",
        "bandgap_numeric",
        "is_nonmetal",
        "formation_energy",
        "passes_formation_filter",
        "phonon_label",
        "dynamically_stable",
    ]
    write_csv(Path(args.output_csv), fieldnames, merged_rows)

    summary = {
        "bandgap_csv": str(Path(args.bandgap_csv).resolve()),
        "formation_selected_csv": str(Path(args.formation_selected_csv).resolve()),
        "phonon_stable_csv": str(Path(args.phonon_stable_csv).resolve()),
        "output_csv": str(Path(args.output_csv).resolve()),
        "counts": {
            "phonon_stable_rows": len(phonon_rows),
            "merged_rows": len(merged_rows),
            "missing_bandgap_rows": missing_bandgap,
            "missing_formation_rows": missing_formation,
        },
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
