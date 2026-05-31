#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
import sys

import torch

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "00_project"))

from paths import ALIGNN_CODE_ROOT, ALIGNN_MOBILITY_MODEL_CONFIG, ALIGNN_MOBILITY_MODEL_CKPT, RUNS_ROOT  # noqa: E402

sys.path.insert(0, str(ALIGNN_CODE_ROOT))

from jarvis.core.atoms import Atoms  # noqa: E402
from alignn.graphs import Graph  # noqa: E402
from alignn.models.alignn_atomwise import ALIGNNAtomWise, ALIGNNAtomWiseConfig  # noqa: E402


def read_csv_rows(path: Path):
    with path.open("r", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_model(config_path: Path, checkpoint_path: Path, device: torch.device):
    config = json.loads(config_path.read_text())
    model_cfg = ALIGNNAtomWiseConfig(**config["model"])
    model = ALIGNNAtomWise(model_cfg)
    state_dict = torch.load(checkpoint_path, map_location="cpu")
    model.load_state_dict(state_dict)
    model = model.to(device)
    model.eval()
    return model


def predict_mobility(cif_path: Path, model, device, cutoff=8, max_neighbors=12):
    atoms = Atoms.from_cif(str(cif_path), use_cif2cell=False)
    g, lg = Graph.atom_dgl_multigraph(
        atoms,
        cutoff=cutoff,
        max_neighbors=max_neighbors,
    )
    with torch.no_grad():
        out = model([g.to(device), lg.to(device)])["out"]
    return float(out.detach().cpu().numpy().flatten()[0])


def main():
    parser = argparse.ArgumentParser(description="Run ALIGNN mobility inference on a CSV of candidate CIFs.")
    parser.add_argument("--model_config_path", default=str(ALIGNN_MOBILITY_MODEL_CONFIG))
    parser.add_argument("--checkpoint_path", default=str(ALIGNN_MOBILITY_MODEL_CKPT))
    parser.add_argument(
        "--input_csv",
        default=str(RUNS_ROOT / "adhoc_mobility_rank" / "03_megnet_formation_energy" / "formation_energy_selected.csv"),
    )
    parser.add_argument(
        "--output_csv",
        default=str(RUNS_ROOT / "adhoc_mobility_rank" / "04_alignn_mobility_rank" / "mobility_predictions.csv"),
    )
    parser.add_argument(
        "--ranked_output_csv",
        default=str(RUNS_ROOT / "adhoc_mobility_rank" / "04_alignn_mobility_rank" / "mobility_ranked_candidates.csv"),
    )
    parser.add_argument(
        "--log_path",
        default=str(RUNS_ROOT / "adhoc_mobility_rank" / "04_alignn_mobility_rank" / "mobility_predict.log"),
    )
    parser.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    device = torch.device(args.device)
    model = load_model(Path(args.model_config_path), Path(args.checkpoint_path), device)
    rows = read_csv_rows(Path(args.input_csv))

    out_rows = []
    log_path = Path(args.log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as log_file:
        for idx, row in enumerate(rows):
            cif_path = Path(row["cif_path"])
            try:
                mobility_score = predict_mobility(cif_path, model, device)
                merged = dict(row)
                merged["mobility_score"] = mobility_score
                out_rows.append(merged)
                print(
                    idx,
                    {
                        "cif_name": merged.get("cif_name", cif_path.name),
                        "mobility_score": mobility_score,
                    },
                )
            except Exception as exc:
                log_file.write(f"{cif_path}\t{exc}\n")

    if out_rows:
        fieldnames = list(out_rows[0].keys())
    elif rows:
        fieldnames = list(rows[0].keys()) + ["mobility_score"]
    else:
        fieldnames = ["cif_name", "cif_path", "bandgap", "is_nonmetal", "formation_energy", "passes_formation_filter", "mobility_score"]
    write_csv(Path(args.output_csv), fieldnames, out_rows)
    ranked_rows = sorted(out_rows, key=lambda row: float(row["mobility_score"]), reverse=True)
    write_csv(Path(args.ranked_output_csv), fieldnames, ranked_rows)
    print(
        {
            "predicted_candidates": len(out_rows),
            "output_csv": args.output_csv,
            "ranked_output_csv": args.ranked_output_csv,
        }
    )


if __name__ == "__main__":
    main()
