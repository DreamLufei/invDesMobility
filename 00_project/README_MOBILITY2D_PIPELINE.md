# Mobility-Oriented Screening Pipeline

This document gives a compact, portable overview of the generation and
screening route. Source `00_project/paths.sh` before running step scripts:

```bash
cd /path/to/invDesMobility
export INVDES_ROOT="$PWD"
source 00_project/paths.sh
```

## Stages

1. Build or update the seed and feedback datasets.
2. Fine-tune the DiffCSP generator.
3. Generate candidate structures.
4. Convert generated tensors to CIF files.
5. Deduplicate generated structures and reference structures.
6. Filter by the target crystal system.
7. Apply surrogate bandgap/nonmetal and formation-energy screens.
8. Optionally apply PhononBench/MatterSim stability screening.
9. Rank survivors with the ALIGNN mobility acquisition model.
10. Export top-k and strict-90-degree CIF queues for first-principles mobility
    validation.

## Small Demonstration Run

```bash
RUN_FINETUNE=0 \
TOTAL_SAMPLES=1000 \
STAGE1_RUN_ID=demo_stage1_generate_1000 \
PIPELINE_RUN_ID=demo_full_pipeline \
bash 05_steps/08_orchestration/run_full_pipeline.sh
```

Expected local outputs:

```text
06_runs/demo_full_pipeline/manifest.json
06_runs/demo_full_pipeline/09_top10_cif/
06_runs/demo_full_pipeline/10_top10_strict90/
```

## Production Run

For a larger generated pool:

```bash
TOTAL_SAMPLES=100000 \
SAMPLES_PER_JOB=1000 \
GPU_LIST=0,1,2,3 \
RUN_ID=generated_100000_structures \
bash 05_steps/03_generate_structures/run_multigpu.sh
```

Then screen a generated CIF directory:

```bash
INPUT_SOURCE_DIR=/path/to/generated_cif \
SOURCE_RUN_LABEL=generated_100000_structures \
RUN_NAME=screened_generated_100000_structures \
TARGET_CRYSTAL_SYSTEM=orthorhombic \
DEDUP_REFERENCE_DIR="$SOURCE_CIF_REFERENCE_ROOT" \
DEDUP_FORMATION_ENERGY_THRESHOLD=0.0 \
DEDUP_BANDGAP_THRESHOLD=0.2 \
TOP_K=30 \
bash 05_steps/08_orchestration/run_dedup_orthorhombic_semiconductor_pipeline.sh
```

Final mobility values should be calculated with the companion `2d-mobility`
repository.
