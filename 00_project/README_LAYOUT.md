# invDesMobility Layout

The repository uses numbered top-level directories to keep long-running
campaign outputs separate from reusable code:

- `00_project`: shared path helpers and project notes.
- `01_code`: source checkouts and workflow adapters.
- `02_envs`: conda environment definitions and install helpers.
- `03_datasets`: local seed, generated and feedback datasets.
- `04_models`: model checkpoints and configuration files.
- `05_steps`: step-level scripts and configs.
- `06_runs`: generated structures, screening outputs and manifests.
- `07_logs`: local logs.
- `08_archive`: optional local archive, not part of the public release.

The public code repository keeps source code, scripts, small metadata and model
configuration files. Large datasets, generated pools, checkpoints and run logs
should be supplied separately.

Common entry points:

- `05_steps/08_orchestration/run_stage1.sh`
- `05_steps/08_orchestration/run_full_pipeline.sh`
- `05_steps/08_orchestration/run_dedup_orthorhombic_semiconductor_pipeline.sh`
- `05_steps/09_closed_loop_feedback/run_closed_loop_round.sh`
