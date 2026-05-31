#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path


def list_cifs(path: Path):
    return sorted(path.glob("*.cif"))


def safe_unlink(path: Path):
    if path.exists() or path.is_symlink():
        path.unlink()


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_label_files(relaxed_dir: Path):
    labels = {}
    label_sources = {}
    for label_path in sorted(relaxed_dir.rglob("L*able.txt")):
        with label_path.open("r") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or "\t" not in line:
                    continue
                cif_stem, status = line.split("\t", 1)
                labels[cif_stem] = status.strip()
                label_sources[cif_stem] = str(label_path.resolve())
    return labels, label_sources


def build_relaxed_lookup(relaxed_dir: Path):
    relaxed_by_stem = {}
    for cif_path in sorted(relaxed_dir.rglob("*_relaxed.cif")):
        stem = cif_path.stem
        if stem.endswith("_relaxed"):
            stem = stem[: -len("_relaxed")]
        relaxed_by_stem[stem] = cif_path.resolve()
    return relaxed_by_stem


def main():
    parser = argparse.ArgumentParser(
        description="Collect PhononBench stability labels and export dynamically stable relaxed CIFs."
    )
    parser.add_argument("--input_dir", required=True)
    parser.add_argument("--relaxed_dir", required=True)
    parser.add_argument("--all_output_csv", required=True)
    parser.add_argument("--stable_output_csv", required=True)
    parser.add_argument("--stable_cif_dir", required=True)
    parser.add_argument("--summary_json", required=True)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    relaxed_dir = Path(args.relaxed_dir)
    stable_cif_dir = Path(args.stable_cif_dir)
    stable_cif_dir.mkdir(parents=True, exist_ok=True)
    for child in stable_cif_dir.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()

    labels, label_sources = parse_label_files(relaxed_dir)
    relaxed_by_stem = build_relaxed_lookup(relaxed_dir)

    all_rows = []
    stable_rows = []
    missing_label_count = 0
    missing_relaxed_cif_count = 0

    for cif_path in list_cifs(input_dir):
        stem = cif_path.stem
        label = labels.get(stem, "")
        relaxed_cif_path = relaxed_by_stem.get(stem)
        is_stable = label.lower() == "stable" and relaxed_cif_path is not None
        exported_cif_path = ""
        note = ""

        if not label:
            missing_label_count += 1
            note = "label_missing"
        elif relaxed_cif_path is None:
            missing_relaxed_cif_count += 1
            note = "relaxed_cif_missing"
        elif label.lower() != "stable":
            note = "phonon_unstable"

        if is_stable:
            link_path = stable_cif_dir / cif_path.name
            safe_unlink(link_path)
            link_path.symlink_to(relaxed_cif_path)
            exported_cif_path = str(link_path)

        row = {
            "cif_name": cif_path.name,
            "source_cif_path": str(cif_path.resolve()),
            "phonon_label": label,
            "label_source": label_sources.get(stem, ""),
            "relaxed_cif_path": str(relaxed_cif_path) if relaxed_cif_path else "",
            "dynamically_stable": is_stable,
            "exported_cif_path": exported_cif_path,
            "note": note,
        }
        all_rows.append(row)
        if is_stable:
            stable_rows.append(dict(row))

    fieldnames = [
        "cif_name",
        "source_cif_path",
        "phonon_label",
        "label_source",
        "relaxed_cif_path",
        "dynamically_stable",
        "exported_cif_path",
        "note",
    ]
    write_csv(Path(args.all_output_csv), fieldnames, all_rows)
    write_csv(Path(args.stable_output_csv), fieldnames, stable_rows)

    summary = {
        "input_dir": str(input_dir),
        "relaxed_dir": str(relaxed_dir),
        "stable_cif_dir": str(stable_cif_dir),
        "counts": {
            "input_cif_total": len(all_rows),
            "labeled_total": sum(1 for row in all_rows if row["phonon_label"]),
            "stable_total": len(stable_rows),
            "unstable_or_failed_total": len(all_rows) - len(stable_rows),
            "missing_label_total": missing_label_count,
            "missing_relaxed_cif_total": missing_relaxed_cif_count,
        },
        "paths": {
            "all_output_csv": args.all_output_csv,
            "stable_output_csv": args.stable_output_csv,
        },
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
