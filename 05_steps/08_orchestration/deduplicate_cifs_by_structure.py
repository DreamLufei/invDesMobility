#!/usr/bin/env python3
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.core import Structure


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def list_cifs(path: Path, recursive: bool = False):
    iterator = path.rglob if recursive else path.glob
    seen = set()
    files = []
    for pattern in ("*.cif", "*.CIF"):
        for cif_path in iterator(pattern):
            resolved = cif_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(cif_path)
    return sorted(files)


def safe_unlink(path: Path):
    if path.exists() or path.is_symlink():
        path.unlink()


def structure_key(structure: Structure):
    comp = structure.composition.fractional_composition
    return tuple(sorted((el.symbol, round(float(frac), 8)) for el, frac in comp.items()))


def parse_cif_pool(cif_paths, dataset_scope, grouped_structures, failure_rows):
    parsed_count = 0
    for cif_path in cif_paths:
        try:
            structure = Structure.from_file(cif_path)
            grouped_structures[structure_key(structure)].append((cif_path, structure))
            parsed_count += 1
        except Exception as exc:
            failure_rows.append(
                {
                    "dataset_scope": dataset_scope,
                    "cif_name": cif_path.name,
                    "cif_path": str(cif_path.resolve()),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return parsed_count


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Deduplicate generated CIFs by crystal-structure matching, keep one "
            "representative per generated duplicate cluster, and drop any generated "
            "cluster that overlaps with a reference CIF library."
        )
    )
    parser.add_argument("--input_dir", required=True)
    parser.add_argument("--reference_dir", action="append", default=[])
    parser.add_argument("--all_output_csv", required=True)
    parser.add_argument("--selected_output_csv", required=True)
    parser.add_argument("--clusters_output_csv", required=True)
    parser.add_argument("--failures_output_csv", required=True)
    parser.add_argument("--selected_cif_dir", required=True)
    parser.add_argument("--summary_json", required=True)
    parser.add_argument("--ltol", type=float, default=0.2)
    parser.add_argument("--stol", type=float, default=0.3)
    parser.add_argument("--angle_tol", type=float, default=5.0)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    reference_dirs = [Path(item) for item in args.reference_dir]
    selected_cif_dir = Path(args.selected_cif_dir)
    selected_cif_dir.mkdir(parents=True, exist_ok=True)
    for child in selected_cif_dir.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()

    matcher = StructureMatcher(
        ltol=args.ltol,
        stol=args.stol,
        angle_tol=args.angle_tol,
        primitive_cell=True,
        scale=True,
    )

    input_cif_paths = list_cifs(input_dir)
    reference_cif_paths = []
    for reference_dir in reference_dirs:
        reference_cif_paths.extend(list_cifs(reference_dir, recursive=True))

    grouped_input = defaultdict(list)
    grouped_reference = defaultdict(list)
    all_rows = []
    selected_rows = []
    cluster_rows = []
    failure_rows = []

    input_parse_success = parse_cif_pool(
        input_cif_paths,
        "input",
        grouped_input,
        failure_rows,
    )
    reference_parse_success = parse_cif_pool(
        reference_cif_paths,
        "reference",
        grouped_reference,
        failure_rows,
    )

    for row in failure_rows:
        if row["dataset_scope"] != "input":
            continue
        all_rows.append(
            {
                "cif_name": row["cif_name"],
                "cif_path": row["cif_path"],
                "reduced_formula": "",
                "num_sites": "",
                "cluster_id": "",
                "cluster_size": "",
                "representative_cif_name": "",
                "representative_cif_path": "",
                "duplicate_of_cif_name": "",
                "matches_reference_dataset": False,
                "matched_reference_cif_name": "",
                "matched_reference_cif_path": "",
                "is_representative": False,
                "kept_for_downstream": False,
                "removal_reason": "input_parse_failed",
                "parse_ok": False,
                "error": row["error"],
            }
        )

    cluster_id = 0
    for key, items in grouped_input.items():
        local_reps = []
        local_clusters = []
        reference_items = grouped_reference.get(key, [])

        for cif_path, structure in items:
            matched = False
            for idx, rep_structure in enumerate(local_reps):
                if matcher.fit(structure, rep_structure):
                    local_clusters[idx]["members"].append((cif_path, structure))
                    matched = True
                    break
            if not matched:
                local_reps.append(structure)
                local_clusters.append(
                    {
                        "representative": (cif_path, structure),
                        "members": [(cif_path, structure)],
                    }
                )

        for cluster in local_clusters:
            cluster_id += 1
            representative_path, representative_structure = cluster["representative"]
            cluster_members = cluster["members"]
            cluster_size = len(cluster_members)
            matched_reference_path = None

            for ref_path, ref_structure in reference_items:
                if matcher.fit(representative_structure, ref_structure):
                    matched_reference_path = ref_path
                    break

            kept_for_downstream = matched_reference_path is None
            removal_reason = (
                "kept_unique_structure"
                if kept_for_downstream
                else "duplicate_of_reference_dataset"
            )

            if kept_for_downstream:
                rep_link = selected_cif_dir / representative_path.name
                safe_unlink(rep_link)
                rep_link.symlink_to(representative_path.resolve())
                selected_rows.append(
                    {
                        "cif_name": representative_path.name,
                        "cif_path": str(rep_link),
                        "source_cif_path": str(representative_path.resolve()),
                        "cluster_id": cluster_id,
                        "cluster_size": cluster_size,
                        "reduced_formula": representative_structure.composition.reduced_formula,
                        "num_sites": len(representative_structure),
                        "matches_reference_dataset": False,
                        "matched_reference_cif_name": "",
                        "matched_reference_cif_path": "",
                    }
                )

            cluster_rows.append(
                {
                    "cluster_id": cluster_id,
                    "representative_cif_name": representative_path.name,
                    "representative_cif_path": str(representative_path.resolve()),
                    "cluster_size": cluster_size,
                    "reduced_formula": representative_structure.composition.reduced_formula,
                    "num_sites": len(representative_structure),
                    "member_cif_names": "|".join(member_path.name for member_path, _ in cluster_members),
                    "matches_reference_dataset": matched_reference_path is not None,
                    "matched_reference_cif_name": matched_reference_path.name if matched_reference_path else "",
                    "matched_reference_cif_path": str(matched_reference_path.resolve()) if matched_reference_path else "",
                    "kept_for_downstream": kept_for_downstream,
                    "removal_reason": removal_reason,
                }
            )

            representative_output_path = (
                str((selected_cif_dir / representative_path.name))
                if kept_for_downstream
                else ""
            )
            for idx, (member_path, member_structure) in enumerate(cluster_members):
                member_reason = removal_reason
                if kept_for_downstream and idx > 0:
                    member_reason = "duplicate_of_generated_representative"

                all_rows.append(
                    {
                        "cif_name": member_path.name,
                        "cif_path": str(member_path.resolve()),
                        "reduced_formula": member_structure.composition.reduced_formula,
                        "num_sites": len(member_structure),
                        "cluster_id": cluster_id,
                        "cluster_size": cluster_size,
                        "representative_cif_name": representative_path.name,
                        "representative_cif_path": representative_output_path,
                        "duplicate_of_cif_name": "" if idx == 0 else representative_path.name,
                        "matches_reference_dataset": matched_reference_path is not None,
                        "matched_reference_cif_name": matched_reference_path.name if matched_reference_path else "",
                        "matched_reference_cif_path": str(matched_reference_path.resolve()) if matched_reference_path else "",
                        "is_representative": idx == 0,
                        "kept_for_downstream": kept_for_downstream and idx == 0,
                        "removal_reason": member_reason,
                        "parse_ok": True,
                        "error": "",
                    }
                )

    write_csv(
        Path(args.all_output_csv),
        [
            "cif_name",
            "cif_path",
            "reduced_formula",
            "num_sites",
            "cluster_id",
            "cluster_size",
            "representative_cif_name",
            "representative_cif_path",
            "duplicate_of_cif_name",
            "matches_reference_dataset",
            "matched_reference_cif_name",
            "matched_reference_cif_path",
            "is_representative",
            "kept_for_downstream",
            "removal_reason",
            "parse_ok",
            "error",
        ],
        all_rows,
    )
    write_csv(
        Path(args.selected_output_csv),
        [
            "cif_name",
            "cif_path",
            "source_cif_path",
            "cluster_id",
            "cluster_size",
            "reduced_formula",
            "num_sites",
            "matches_reference_dataset",
            "matched_reference_cif_name",
            "matched_reference_cif_path",
        ],
        selected_rows,
    )
    write_csv(
        Path(args.clusters_output_csv),
        [
            "cluster_id",
            "representative_cif_name",
            "representative_cif_path",
            "cluster_size",
            "reduced_formula",
            "num_sites",
            "member_cif_names",
            "matches_reference_dataset",
            "matched_reference_cif_name",
            "matched_reference_cif_path",
            "kept_for_downstream",
            "removal_reason",
        ],
        cluster_rows,
    )
    write_csv(
        Path(args.failures_output_csv),
        ["dataset_scope", "cif_name", "cif_path", "error"],
        failure_rows,
    )

    duplicate_removed_total = sum(
        max(int(row["cluster_size"]) - 1, 0)
        for row in cluster_rows
    )
    reference_overlap_cluster_total = sum(
        1
        for row in cluster_rows
        if row["matches_reference_dataset"]
    )
    reference_overlap_removed_total = sum(
        int(row["cluster_size"])
        for row in cluster_rows
        if row["matches_reference_dataset"]
    )

    summary = {
        "input_dir": str(input_dir),
        "reference_dirs": [str(item) for item in reference_dirs],
        "matcher": {
            "ltol": args.ltol,
            "stol": args.stol,
            "angle_tol": args.angle_tol,
            "primitive_cell": True,
            "scale": True,
        },
        "counts": {
            "input_cif_total": len(input_cif_paths),
            "input_parse_success": input_parse_success,
            "input_parse_failures": len([row for row in failure_rows if row["dataset_scope"] == "input"]),
            "reference_cif_total": len(reference_cif_paths),
            "reference_parse_success": reference_parse_success,
            "reference_parse_failures": len([row for row in failure_rows if row["dataset_scope"] == "reference"]),
            "unique_cif_total": len(selected_rows),
            "duplicate_removed_total": duplicate_removed_total,
            "duplicate_cluster_total": sum(1 for row in cluster_rows if int(row["cluster_size"]) > 1),
            "largest_cluster_size": max((int(row["cluster_size"]) for row in cluster_rows), default=0),
            "reference_overlap_cluster_total": reference_overlap_cluster_total,
            "reference_overlap_removed_total": reference_overlap_removed_total,
        },
        "paths": {
            "all_output_csv": args.all_output_csv,
            "selected_output_csv": args.selected_output_csv,
            "clusters_output_csv": args.clusters_output_csv,
            "failures_output_csv": args.failures_output_csv,
            "selected_cif_dir": args.selected_cif_dir,
        },
    }

    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
