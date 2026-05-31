# Deployment And Fine-Tuning Notes

This note summarizes the portable setup for the inverse-design workflow.
Machine-specific paths, scheduler commands and model locations should be set in
the shell environment rather than committed to the repository.

## Root Paths

```bash
cd /path/to/invDesMobility
export INVDES_ROOT="$PWD"
source 00_project/paths.sh
```

The path helper defines the common directories used by the step scripts:

- `01_code/` for source checkouts and adapters.
- `02_envs/` for conda environment definitions.
- `03_datasets/` for seed, feedback and ranking datasets.
- `04_models/` for external model checkpoints and local fine-tuned outputs.
- `05_steps/` for step-level scripts.
- `06_runs/` and `07_logs/` for local outputs.

## Environments

Install only the environments needed for the stages you plan to run:

```bash
bash 02_envs/install_diffcsp_gen.sh
bash 02_envs/install_alignn_screen.sh
bash 02_envs/install_megnet_form.sh
bash 02_envs/install_phononbench_mattersim.sh
```

The scripts are templates. Adjust CUDA, PyTorch, DGL and scheduler details for
the target cluster.

## Typical Route

```bash
source 00_project/paths.sh

RUN_FINETUNE=0 \
TOTAL_SAMPLES=1000 \
STAGE1_RUN_ID=demo_stage1_generate_1000 \
PIPELINE_RUN_ID=demo_full_pipeline \
bash 05_steps/08_orchestration/run_full_pipeline.sh
```

For production campaigns, provide trained model checkpoints and larger datasets
through `03_datasets/` and `04_models/`, then increase `TOTAL_SAMPLES`.

## Closed-Loop Feedback

Feedback utilities live under `05_steps/09_closed_loop_feedback/`. They expect
a completed `2d-mobility` batch root and write trusted feedback datasets,
round manifests and model-training inputs under the local run/model/data
directories.

Use the companion `invdesmobility_loop` package for a higher-level command-line
wrapper around a complete round.
