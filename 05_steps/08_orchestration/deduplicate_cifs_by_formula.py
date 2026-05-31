#!/usr/bin/env python3
import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pymatgen.core import Composition, Structure


FORMULA_TAGS = (
    "_chemical_formula_sum",
    "_chemical_formula_structural",
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def list_cifs(path: Path):
    if path.is_file():
        return [path] if path.suffix.lower() == ".cif" else []
    files = []
    for pattern in ("*.cif", "*.CIF"):
        files.extend(path.glob(pattern))
    return sorted(files)


def clean_value(value: str):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.strip()


def normalize_formula(formula: str):
    return Composition(clean_value(formula)).reduced_formula


def parse_formula_from_cif(cif_path: Path):
    try:
        with cif_path.open("r", errors="replace") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                for tag in FORMULA_TAGS:
                    if stripped.startswith(tag):
                        parts = stripped.split(maxsplit=1)
                        if len(parts) == 2:
                            return normalize_formula(parts[1]), "cif_header"
                if line_number > 200:
                    break
    except Exception:
        pass

    structure = Structure.from_file(cif_path)
    return structure.composition.reduced_formula, "pymatgen_structure"


def safe_unlink(path: Path):
    if path.exists() or path.is_symlink():
        path.unlink()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Deduplicate generated CIFs by reduced chemical formula only. One "
            "current CIF is kept per new formula; any formula already present in "
            "the history CIF pools is removed."
        )
    )
    parser.add_argument("--input_dir", required=True)
    parser.add_argument("--history_dir", action="append", default=[])
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--progress_every", type=int, default=50000)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    history_dirs = [Path(item) for item in args.history_dir]
    output_dir = Path(args.output_dir)
    selected_cif_dir = output_dir / "formula_unique_cif"
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_cif_dir.mkdir(parents=True, exist_ok=True)
    for child in selected_cif_dir.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()

    started_at = utc_now()
    input_cif_paths = list_cifs(input_dir)
    history_cif_paths = []
    for history_dir in history_dirs:
        history_cif_paths.extend(list_cifs(history_dir))

    history_counts = Counter()
    history_first_path = {}
    history_failures = []

    print(f"[formula-dedup] history CIFs: {len(history_cif_paths)}", flush=True)
    for index, cif_path in enumerate(history_cif_paths, start=1):
        try:
            formula, parse_method = parse_formula_from_cif(cif_path)
            history_counts[formula] += 1
            history_first_path.setdefault(formula, str(cif_path.resolve()))
        except Exception as exc:
            history_failures.append(
                {
                    "dataset_scope": "history",
                    "cif_name": cif_path.name,
                    "cif_path": str(cif_path.resolve()),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        if args.progress_every and index % args.progress_every == 0:
            print(
                f"[formula-dedup] parsed history {index}/{len(history_cif_paths)}",
                flush=True,
            )

    all_fields = [
        "cif_name",
        "cif_path",
        "reduced_formula",
        "formula_occurrence_index",
        "representative_cif_name",
        "representative_cif_path",
        "matches_history_formula",
        "matched_history_cif_path",
        "kept_for_downstream",
        "removal_reason",
        "parse_method",
        "parse_ok",
        "error",
    ]
    selected_fields = [
        "cif_name",
        "cif_path",
        "source_cif_path",
        "reduced_formula",
        "current_formula_count",
        "history_formula_count",
        "history_example_cif_path",
        "parse_method",
    ]
    failure_fields = ["dataset_scope", "cif_name", "cif_path", "error"]

    current_counts = Counter()
    current_parse_success = 0
    selected_by_formula = {}
    status_counts = Counter()
    input_failures = []

    all_output_csv = output_dir / "formula_all.csv"
    print(f"[formula-dedup] current CIFs: {len(input_cif_paths)}", flush=True)
    with all_output_csv.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=all_fields)
        writer.writeheader()

        for index, cif_path in enumerate(input_cif_paths, start=1):
            try:
                formula, parse_method = parse_formula_from_cif(cif_path)
                current_parse_success += 1
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                input_failures.append(
                    {
                        "dataset_scope": "input",
                        "cif_name": cif_path.name,
                        "cif_path": str(cif_path.resolve()),
                        "error": error,
                    }
                )
                status_counts["input_parse_failed"] += 1
                writer.writerow(
                    {
                        "cif_name": cif_path.name,
                        "cif_path": str(cif_path.resolve()),
                        "reduced_formula": "",
                        "formula_occurrence_index": "",
                        "representative_cif_name": "",
                        "representative_cif_path": "",
                        "matches_history_formula": False,
                        "matched_history_cif_path": "",
                        "kept_for_downstream": False,
                        "removal_reason": "input_parse_failed",
                        "parse_method": "",
                        "parse_ok": False,
                        "error": error,
                    }
                )
                continue

            current_counts[formula] += 1
            occurrence_index = current_counts[formula]
            source_path = str(cif_path.resolve())
            history_count = history_counts.get(formula, 0)
            history_example = history_first_path.get(formula, "")

            if history_count:
                status = "duplicate_of_history_formula"
                kept = False
                rep_name = ""
                rep_path = ""
            elif formula not in selected_by_formula:
                status = "kept_new_formula"
                kept = True
                rep_link = selected_cif_dir / cif_path.name
                safe_unlink(rep_link)
                rep_link.symlink_to(cif_path.resolve())
                rep_name = cif_path.name
                rep_path = str(rep_link)
                selected_by_formula[formula] = {
                    "cif_name": cif_path.name,
                    "cif_path": str(rep_link),
                    "source_cif_path": source_path,
                    "reduced_formula": formula,
                    "current_formula_count": 0,
                    "history_formula_count": history_count,
                    "history_example_cif_path": history_example,
                    "parse_method": parse_method,
                }
            else:
                status = "duplicate_of_current_formula_representative"
                kept = False
                rep_name = selected_by_formula[formula]["cif_name"]
                rep_path = selected_by_formula[formula]["cif_path"]

            status_counts[status] += 1
            writer.writerow(
                {
                    "cif_name": cif_path.name,
                    "cif_path": source_path,
                    "reduced_formula": formula,
                    "formula_occurrence_index": occurrence_index,
                    "representative_cif_name": rep_name,
                    "representative_cif_path": rep_path,
                    "matches_history_formula": bool(history_count),
                    "matched_history_cif_path": history_example,
                    "kept_for_downstream": kept,
                    "removal_reason": status,
                    "parse_method": parse_method,
                    "parse_ok": True,
                    "error": "",
                }
            )

            if args.progress_every and index % args.progress_every == 0:
                print(
                    "[formula-dedup] parsed current "
                    f"{index}/{len(input_cif_paths)}; kept={len(selected_by_formula)}; "
                    f"distinct_current={len(current_counts)}",
                    flush=True,
                )

    selected_rows = []
    for formula, row in sorted(selected_by_formula.items()):
        row = dict(row)
        row["current_formula_count"] = current_counts[formula]
        selected_rows.append(row)

    history_rows = [
        {
            "reduced_formula": formula,
            "history_formula_count": count,
            "history_example_cif_path": history_first_path.get(formula, ""),
        }
        for formula, count in sorted(history_counts.items())
    ]

    failures = history_failures + input_failures
    write_csv(output_dir / "formula_unique_candidates.csv", selected_fields, selected_rows)
    write_csv(
        output_dir / "history_formulas.csv",
        ["reduced_formula", "history_formula_count", "history_example_cif_path"],
        history_rows,
    )
    write_csv(output_dir / "formula_failures.csv", failure_fields, failures)

    completed_at = utc_now()
    summary = {
        "started_at": started_at,
        "completed_at": completed_at,
        "input_dir": str(input_dir),
        "history_dirs": [str(item) for item in history_dirs],
        "output_dir": str(output_dir),
        "current_cif_total": len(input_cif_paths),
        "current_parse_success": current_parse_success,
        "current_parse_failures": len(input_failures),
        "current_distinct_formula_total": len(current_counts),
        "history_cif_total": len(history_cif_paths),
        "history_parse_success": len(history_cif_paths) - len(history_failures),
        "history_parse_failures": len(history_failures),
        "history_distinct_formula_total": len(history_counts),
        "kept_unique_formula_total": len(selected_rows),
        "removed_history_formula_total": status_counts["duplicate_of_history_formula"],
        "removed_current_formula_duplicate_total": status_counts[
            "duplicate_of_current_formula_representative"
        ],
        "status_counts": dict(status_counts),
        "formula_all_csv": str(all_output_csv),
        "selected_output_csv": str(output_dir / "formula_unique_candidates.csv"),
        "selected_cif_dir": str(selected_cif_dir),
        "history_formulas_csv": str(output_dir / "history_formulas.csv"),
        "failures_output_csv": str(output_dir / "formula_failures.csv"),
    }
    with (output_dir / "formula_summary.json").open("w") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)

    print(
        "[formula-dedup] completed: "
        f"kept={summary['kept_unique_formula_total']} "
        f"current_distinct={summary['current_distinct_formula_total']} "
        f"history_distinct={summary['history_distinct_formula_total']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
