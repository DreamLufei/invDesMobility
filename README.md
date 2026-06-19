# invDesMobility

`invDesMobility` contains a generative inverse-design and screening workflow
for candidate two-dimensional materials. It prepares feedback datasets,
fine-tunes a DiffCSP generator, generates candidate structures, deduplicates
the generated pool, applies surrogate electronic and stability filters, ranks
surviving candidates with an ALIGNN mobility acquisition model and exports
validation queues.

First-principles mobility labels are assigned by the companion VASP-based
runtime `2d-mobility`. This repository owns generation, screening, ranking and
feedback data preparation; it does not distribute VASP inputs, pseudopotentials
or completed first-principles calculation folders.

## What Is Included

- `00_project/`: shared path helpers and high-level pipeline notes.
- `01_code/`: local source checkouts and adapters used by the workflow,
  including DiffCSP, ALIGNN and PhononBench-related code.
- `02_envs/`: conda environment files and installation helpers.
- `03_datasets/04_metadata/`: small public metadata files.
- `04_models/`: model configuration JSON files only; weights are excluded.
- `05_steps/`: step-level scripts for dataset construction, generator
  fine-tuning, structure generation, filtering, mobility ranking and feedback.
- `06_runs/` and `07_logs/`: placeholders for local run outputs and logs.
- `tests/`: lightweight tests for closed-loop feedback helpers.

The public repository is intentionally small. Large generated pools, training
datasets, checkpoints, run directories and raw VASP results should be stored in
an external data/model archive.

## External artifacts

This repository intentionally excludes large source-data tables, generated pools, trained checkpoints and raw first-principles outputs. Processed source data and retained feedback records are archived on Zenodo:

- Zenodo source-data archive: https://doi.org/10.5281/zenodo.20475023

Released DiffCSP generator checkpoints are available on Hugging Face:

- InvDesMobility DiffCSP generator checkpoints: https://huggingface.co/DreamLufei

The companion evidence website is available at:

- https://dreamlufei.github.io/invDesMobility/

## Requirements

The full workflow uses several separate scientific Python environments:

- DiffCSP generation and fine-tuning.
- ALIGNN bandgap/nonmetal and mobility ranking.
- MEGNet formation-energy screening.
- PhononBench/MatterSim stability screening.

Install helpers are provided in `02_envs/`. They assume `conda` or `mamba` is
available and may need small edits for the CUDA/PyTorch versions on a new
cluster.

## Installation

```bash
git clone https://github.com/DreamLufei/invDesMobility.git
cd invDesMobility

source 00_project/paths.sh
bash 02_envs/install_diffcsp_gen.sh
bash 02_envs/install_alignn_screen.sh
bash 02_envs/install_megnet_form.sh
```

Install the PhononBench/MatterSim environment only if you plan to run the
stability-screening step:

```bash
bash 02_envs/install_phononbench_mattersim.sh
```

## Path Configuration

The repository uses `00_project/paths.sh` and `00_project/paths.py` as central
path definitions. By default, `INVDES_ROOT` resolves to the current repository
root when those helpers are loaded from this checkout.

For custom layouts:

```bash
export INVDES_ROOT=/path/to/invDesMobility
source 00_project/paths.sh
```

Large inputs expected by the scripts include:

```text
03_datasets/01_source_cif/
03_datasets/02_diffcsp_dataset/
03_datasets/03_alignn_mobility_dataset/
04_models/01_diffcsp_generator/
04_models/02_alignn_bandgap_nonmetal/
04_models/03_megnet_formation_energy/
04_models/04_alignn_mobility/
```

These directories are not populated in the public code repository.

## Running The Pipeline

The orchestrated route is:

1. Build or update the seed/feedback dataset.
2. Fine-tune the DiffCSP generator.
3. Generate a candidate structure pool.
4. Deduplicate generated structures and remove known reference structures.
5. Filter by target structure constraints.
6. Apply electronic and stability screening.
7. Rank surviving candidates with the ALIGNN mobility acquisition model.
8. Export a top-k validation queue for first-principles mobility calculations.

A small smoke-style run can be launched with:

```bash
source 00_project/paths.sh

STAGE1_RUN_ID=demo_stage1_generate_1000 \
PIPELINE_RUN_ID=demo_full_pipeline \
TOTAL_SAMPLES=1000 \
RUN_FINETUNE=0 \
bash 05_steps/08_orchestration/run_full_pipeline.sh
```

Full campaigns increase `TOTAL_SAMPLES` and use trained generator/model
artifacts supplied outside this repository.

## Closed-Loop Feedback

The feedback scripts in `05_steps/09_closed_loop_feedback/` extract trusted
first-principles validation results, build feedback-augmented DiffCSP and
ALIGNN datasets and prepare the next generation round.

Typical entry point:

```bash
bash 05_steps/09_closed_loop_feedback/run_closed_loop_round.sh
```

The companion `invdesmobility_loop` repository provides a higher-level
orchestration bridge for running these steps together with downstream
`2d-mobility` batches.

## Tests

```bash
python -m pytest -q tests
```

The tests cover the lightweight feedback and orchestration helpers. Full
generation, screening and ranking runs require the external scientific
environments and model/data artifacts described above.

## Public-Release Boundaries

This repository intentionally excludes:

- trained generator checkpoints and ALIGNN/MEGNet weights;
- generated `10^5` to `5*10^5` candidate pools;
- full `06_runs/`, `07_logs/` and archival folders;
- VASP `POTCAR` files and raw VASP calculation directories;
- private environment files or machine-specific secrets.

See [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) for an additional checklist.

## License

This repository is released under the MIT License; see `LICENSE`.
