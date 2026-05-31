#!/usr/bin/env python
import argparse
import json
from pathlib import Path
import sys

import distutils.version  # noqa: F401
import hydra
import torch
from omegaconf import OmegaConf
from hydra.experimental import compose, initialize_config_dir

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "00_project"))

from paths import DIFFCSP_ROOT, LOGS_ROOT  # noqa: E402


def shape_of(value):
    if hasattr(value, "shape"):
        return list(value.shape)
    return None


def json_safe(value):
    if OmegaConf.is_config(value):
        return OmegaConf.to_container(value, resolve=True)
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def main():
    parser = argparse.ArgumentParser(description="Check DiffCSP checkpoint compatibility.")
    parser.add_argument("--ckpt_path", required=True)
    parser.add_argument("--dataset_name", default="mobility2d_highquality280")
    parser.add_argument("--expname", default="mobility2d_highquality280_ft_v1")
    parser.add_argument(
        "--report_path",
        default=str(LOGS_ROOT / "02_finetune_generator" / "ckpt_compatibility_mobility2d_highquality280.json"),
    )
    parser.add_argument(
        "--filtered_ckpt_path",
        default=str(LOGS_ROOT / "02_finetune_generator" / "ckpt_compatibility_filtered.ckpt"),
    )
    args = parser.parse_args()

    diffcsp_root = DIFFCSP_ROOT
    conf_dir = diffcsp_root / "conf"
    ckpt_path = Path(args.ckpt_path)
    report_path = Path(args.report_path)
    filtered_ckpt_path = Path(args.filtered_ckpt_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with initialize_config_dir(str(conf_dir)):
        cfg = compose(
            config_name="default",
            overrides=[
                f"data={args.dataset_name}",
                "model=diffusion_w_type",
                f"expname={args.expname}",
            ],
        )

    model = hydra.utils.instantiate(
        cfg.model,
        optim=cfg.optim,
        data=cfg.data,
        logging=cfg.logging,
        _recursive_=False,
    )

    current_state = model.state_dict()
    checkpoint = torch.load(ckpt_path, map_location="cpu")
    checkpoint_state = checkpoint["state_dict"] if "state_dict" in checkpoint else checkpoint

    current_keys = set(current_state.keys())
    checkpoint_keys = set(checkpoint_state.keys())
    shared_keys = sorted(current_keys & checkpoint_keys)

    missing_in_ckpt = sorted(current_keys - checkpoint_keys)
    extra_in_ckpt = sorted(checkpoint_keys - current_keys)
    shape_mismatches = []
    loadable_keys = []

    for key in shared_keys:
        current_shape = shape_of(current_state[key])
        checkpoint_shape = shape_of(checkpoint_state[key])
        if current_shape != checkpoint_shape:
            shape_mismatches.append(
                {
                    "key": key,
                    "current_shape": current_shape,
                    "checkpoint_shape": checkpoint_shape,
                }
            )
        else:
            loadable_keys.append(key)

    compatible = not missing_in_ckpt and not shape_mismatches
    filtered_checkpoint = dict(checkpoint)
    filtered_checkpoint["state_dict"] = {
        key: checkpoint_state[key] for key in loadable_keys
    }
    torch.save(filtered_checkpoint, filtered_ckpt_path)

    checkpoint_epoch = checkpoint.get("epoch")
    checkpoint_step = checkpoint.get("global_step")
    resume_ckpt_name = "epoch=0-step=0.ckpt"
    if checkpoint_epoch is not None and checkpoint_step is not None:
        resume_ckpt_name = f"epoch={checkpoint_epoch}-step={checkpoint_step}.ckpt"

    hyper_parameters = checkpoint.get("hyper_parameters", {})
    hyper_subset = {
        key: hyper_parameters.get(key)
        for key in [
            "time_dim",
            "latent_dim",
            "cost_coord",
            "cost_lattice",
            "cost_type",
            "decoder",
            "beta_scheduler",
            "sigma_scheduler",
        ]
        if key in hyper_parameters
    }

    report = {
        "checkpoint_path": str(ckpt_path),
        "report_path": str(report_path),
        "filtered_ckpt_path": str(filtered_ckpt_path),
        "compatible": compatible,
        "checkpoint_epoch": checkpoint_epoch,
        "checkpoint_global_step": checkpoint_step,
        "resume_ckpt_name": resume_ckpt_name,
        "missing_in_ckpt": missing_in_ckpt,
        "extra_in_ckpt": extra_in_ckpt,
        "shape_mismatches": shape_mismatches,
        "loadable_key_count": len(loadable_keys),
        "current_key_count": len(current_state),
        "checkpoint_key_count": len(checkpoint_state),
        "lightning_version": checkpoint.get("pytorch-lightning_version"),
        "hyper_parameters_subset": json_safe(hyper_subset),
    }

    report_path.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps(report, indent=2, sort_keys=True))

    if compatible:
        print("[check_diffcsp_ckpt_compat] compatible: strict resume is possible")
        return

    print("[check_diffcsp_ckpt_compat] incompatible: inspect report and filtered checkpoint")
    raise SystemExit(2)


if __name__ == "__main__":
    main()
