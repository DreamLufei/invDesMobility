import argparse
import csv
import os
import time
from pathlib import Path

from megnet.models import MEGNetModel
from megnet.utils.models import load_model
from pymatgen.core import Structure


DEFAULT_ROOT = Path(os.environ.get("INVDES_ROOT", Path(__file__).resolve().parents[2])).resolve()
DEFAULT_MODEL_PATH = str(DEFAULT_ROOT / "04_models/03_megnet_formation_energy/FormEGNN-weight.hdf5")
DEFAULT_MODEL_CONFIG_PATH = str(DEFAULT_ROOT / "04_models/03_megnet_formation_energy/megnet_formation_energy.hdf5.json")
DEFAULT_CIF_DIR = str(DEFAULT_ROOT / "generated_cif")
DEFAULT_INPUT_CSV = str(DEFAULT_ROOT / "results/nonmetal_candidates.csv")
DEFAULT_OUTPUT_CSV = str(DEFAULT_ROOT / "results/formation_energy_predictions.csv")
DEFAULT_LOG_PATH = str(DEFAULT_ROOT / "07_logs/formation_energy_predictions.log")


def save_csv(path: str, head: list, data_list: list):
    with open(path, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(head)
        writer.writerows(data_list)
    print(f"CSV file saved, {len(data_list)} rows, located at {path}")


def ensure_model_sidecar(model_path: Path, config_path: Path):
    sidecar_path = Path(str(model_path) + ".json")
    if sidecar_path.exists():
        return sidecar_path
    if not config_path.exists():
        raise FileNotFoundError(f"Missing MEGNet config file: {config_path}")
    sidecar_path.symlink_to(config_path)
    return sidecar_path


def load_megnet_model(model_path: str):
    try:
        return load_model(model_path)
    except Exception:
        return MEGNetModel.from_file(model_path)


def gather_cif_paths(cif_dir: Path, input_csv: Path):
    if input_csv.exists():
        cif_paths = []
        with input_csv.open("r", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                cif_path = row.get("cif_path")
                if cif_path:
                    cif_paths.append(cif_path)
        if cif_paths:
            return cif_paths

    if not cif_dir.exists():
        raise FileNotFoundError(f"Missing CIF directory: {cif_dir}")
    return [str(path) for path in sorted(cif_dir.glob("*.cif"))]


def load_cif_to_structure(cif_path: str):
    if cif_path.endswith(".cif"):
        with open(cif_path, "r") as cif_file:
            cif_str = cif_file.read()
        return Structure.from_str(cif_str, fmt="cif")
    return Structure.from_file(cif_path)


def main():
    parser = argparse.ArgumentParser(description="Predict formation energy with MEGNet.")
    parser.add_argument("--model_path", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--model_config_path", default=DEFAULT_MODEL_CONFIG_PATH)
    parser.add_argument("--cif_dir", default=DEFAULT_CIF_DIR)
    parser.add_argument("--input_csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--output_csv", default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--log_path", default=DEFAULT_LOG_PATH)
    args = parser.parse_args()

    model_path = Path(args.model_path)
    config_path = Path(args.model_config_path)
    cif_dir = Path(args.cif_dir)
    input_csv = Path(args.input_csv)
    output_csv = Path(args.output_csv)
    log_path = Path(args.log_path)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if not model_path.exists():
        raise FileNotFoundError(f"Missing MEGNet model file: {model_path}")

    ensure_model_sidecar(model_path, config_path)
    model = load_megnet_model(str(model_path))
    cif_file_paths = gather_cif_paths(cif_dir, input_csv)

    data = []
    t1 = time.time()
    with log_path.open("a") as log_file:
        for idx, path in enumerate(cif_file_paths):
            try:
                structure = load_cif_to_structure(path)
                prediction = model.predict_structure(structure).ravel()[0]
                cif_name = os.path.basename(path)
                data.append([cif_name, path, prediction])
                t2 = time.time()
                print(
                    idx,
                    f"elapsed: {(t2 - t1) / 60:.3f} min",
                    f"current: {cif_name}",
                    f"prediction: {prediction}",
                )
            except Exception as exc:
                log_file.write(f"{path}\t{exc}\n")

    save_csv(
        path=str(output_csv),
        head=["file_name", "cif_path", "formation_energy"],
        data_list=data,
    )


if __name__ == "__main__":
    main()
