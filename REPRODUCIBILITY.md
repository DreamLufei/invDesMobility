# Reproducibility guide

This guide documents how to reproduce the generative inverse-design and
screening side of the InvDesMobility study. It is written for code review,
archival release and reuse by another group.

## What this repository reproduces

This repository reproduces:

- construction of seed and feedback datasets for DiffCSP and ALIGNN;
- generator fine-tuning and candidate generation;
- structure deduplication against generated and reference pools;
- orthorhombic and strict-90-degree structural filters;
- surrogate formation-energy screening;
- PhononBench/MatterSim dynamical-stability screening;
- ALIGNN bandgap/nonmetal screening;
- ALIGNN mobility acquisition ranking;
- top-k CIF export for first-principles mobility validation.

It does not assign final mobility labels. Final carrier- and direction-resolved
mobility values are assigned by the companion VASP workflow in
`2d-mobility`.

## Companion repositories

- Mobility runtime: https://github.com/DreamLufei/2d-mobility
- Closed-loop bridge: https://github.com/DreamLufei/invdesmobility_loop

For a full closed-loop campaign, clone all three repositories side by side:

```bash
git clone https://github.com/DreamLufei/2d-mobility.git
git clone https://github.com/DreamLufei/invDesMobility.git
git clone https://github.com/DreamLufei/invdesmobility_loop.git
```

## Environment setup

The pipeline uses multiple environments because the upstream tools require
different Python, PyTorch and TensorFlow stacks.

```bash
cd invDesMobility
bash 02_envs/install_diffcsp_gen.sh
bash 02_envs/install_alignn_screen.sh
bash 02_envs/install_megnet_form.sh
bash 02_envs/install_phononbench_mattersim.sh
```

Cluster-specific changes may be needed for CUDA, DGL and scheduler commands.
Record any such changes in a local lab notebook or an archival run manifest.

## Required external artifacts

The public GitHub repository intentionally excludes large files. To reproduce
the manuscript-scale campaign, obtain or regenerate:

- seed CIF library and mobility seed tables;
- DiffCSP seed/feedback CSV splits;
- trained DiffCSP checkpoints;
- trained ALIGNN bandgap and mobility models;
- generated candidate pools;
- screening and top-k CSV manifests;
- retained first-principles feedback records from `2d-mobility`.

Recommended archival layout:

```text
data_archive/
  seed/
  diffcsp_datasets/
  alignn_datasets/
  models/
  generated_pools/
  screening_runs/
  closed_loop_feedback/
  figure_source_data/
```

Copy or symlink those artifacts into the paths expected by
`00_project/paths.sh`, or override the paths in your shell before running the
pipeline.

## Smoke test

After installing the environments, run a small end-to-end smoke test:

```bash
cd invDesMobility
source 00_project/paths.sh

STAGE1_RUN_ID=demo_stage1_generate_1000 \
PIPELINE_RUN_ID=demo_full_pipeline \
RUN_FINETUNE=0 \
bash 05_steps/08_orchestration/run_full_pipeline.sh
```

Expected outputs:

```text
06_runs/demo_full_pipeline/manifest.json
06_runs/demo_full_pipeline/09_top10_cif/top10_candidates.csv
06_runs/demo_full_pipeline/10_top10_strict90/top10_candidates_strict90.csv
06_runs/demo_full_pipeline/10_top10_strict90/strict90_cif/
```

## Manuscript-scale generation and screening

Generate a `10^5`-structure pool:

```bash
cd invDesMobility
source 00_project/paths.sh

TOTAL_SAMPLES=100000 \
SAMPLES_PER_JOB=1000 \
GPU_LIST=0,1,2,3 \
LABEL_PREFIX=gen100000 \
CONVERT_TO_CIF=1 \
RUN_ID=generated_100000_structures_from_feedback_model \
bash 05_steps/03_generate_structures/run_multigpu.sh
```

Screen and rank a completed generated pool:

```bash
INPUT_SOURCE_DIR="$RUNS_ROOT/generated_100000_structures_from_feedback_model/03_generate_structures/generated_cif" \
SOURCE_RUN_LABEL=generated_100000_structures_from_feedback_model \
RUN_NAME=screened_generated_100000_feedback_model \
TARGET_CRYSTAL_SYSTEM=orthorhombic \
DEDUP_REFERENCE_DIR="$SOURCE_CIF_REFERENCE_ROOT" \
DEDUP_FORMATION_ENERGY_THRESHOLD=0.0 \
DEDUP_BANDGAP_THRESHOLD=1.0 \
PHONONBENCH_DIM="2 2 2" \
PHONONBENCH_GPU_LIST=0,1,2,3 \
PHONONBENCH_SUBPARTS_PER_GPU=1 \
TOP_K=10 \
bash 05_steps/08_orchestration/run_dedup_orthorhombic_semiconductor_pipeline.sh
```

The exported strict90 CIFs are the input queue for `2d-mobility`.

## Closed-loop feedback

The feedback utilities live in `05_steps/09_closed_loop_feedback/`.
They extract trusted channel-level labels from completed `2d-mobility` batch
runs, build feedback-augmented DiffCSP and ALIGNN datasets, and archive trusted
relaxed structures for future deduplication.

Round-specific DiffCSP configs are tracked under:

```text
01_code/InvDesFlow/DiffCSP/conf/data/mobility2d_feedback_round_01.yaml
01_code/InvDesFlow/DiffCSP/conf/data/mobility2d_feedback_round_02.yaml
01_code/InvDesFlow/DiffCSP/conf/data/mobility2d_feedback_round_03.yaml
01_code/InvDesFlow/DiffCSP/conf/data/mobility2d_feedback_round_04.yaml
```

The bridge repository provides the higher-level command-line wrapper for these
steps.

## Verification

Run repository tests:

```bash
python -m pytest -q tests
```

For screening changes, also run a small pipeline on a known CIF subset and
inspect:

- `manifest.json` stage paths and counts;
- deduplication reports;
- bandgap/nonmetal CSV;
- formation-energy CSV;
- PhononBench stability CSV;
- top-k export CSV and strict90 CIF directory.

## Public-release and NCS notes

Nature Computational Science expects code and data sufficient for others to
replicate and build on the published claims. For this repository:

- keep source code, configs, small metadata and step scripts in GitHub;
- deposit large generated pools, source-data tables and model checkpoints in a
  DOI-backed archive such as Zenodo;
- do not upload VASP `POTCAR` files, private credentials, local scheduler logs
  or raw VASP directories to GitHub;
- cite the GitHub repositories and DOI archive in the manuscript Code
  Availability and Data Availability statements.

Recommended manuscript Code Availability wording:

```text
The generative inverse-design, screening and acquisition-ranking code is
available at https://github.com/DreamLufei/invDesMobility.
```
