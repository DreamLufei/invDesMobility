import os
from pathlib import Path


INVDES_ROOT = Path(os.environ.get("INVDES_ROOT", Path(__file__).resolve().parents[1])).resolve()
PROJECT_ROOT = INVDES_ROOT / "00_project"
CODE_ROOT = INVDES_ROOT / "01_code"
INV_DES_FLOW_ROOT = CODE_ROOT / "InvDesFlow"
PHONONBENCH_ROOT = CODE_ROOT / "PhononBench"
MATTERSIM_ROOT = CODE_ROOT / "MatterSim"
ENVS_ROOT = INVDES_ROOT / "02_envs"
DATASETS_ROOT = INVDES_ROOT / "03_datasets"
MODELS_ROOT = INVDES_ROOT / "04_models"
STEPS_ROOT = INVDES_ROOT / "05_steps"
RUNS_ROOT = INVDES_ROOT / "06_runs"
LOGS_ROOT = INVDES_ROOT / "07_logs"
LOGS_BY_RUN_ROOT = LOGS_ROOT / "09_runs_by_name"
ARCHIVE_ROOT = INVDES_ROOT / "08_archive"

SOURCE_CIF_DIR = DATASETS_ROOT / "01_source_cif" / "high_quality_280"
SOURCE_CIF_REFERENCE_ROOT = DATASETS_ROOT / "01_source_cif"
DIFFCSP_DATASET_DIR = DATASETS_ROOT / "02_diffcsp_dataset" / "mobility2d_highquality280"
ALIGNN_MOBILITY_DATA_DIR = DATASETS_ROOT / "03_alignn_mobility_dataset" / "mobility_reg_v1"
METADATA_DIR = DATASETS_ROOT / "04_metadata"

DIFFCSP_ROOT = INV_DES_FLOW_ROOT / "DiffCSP"
ALIGNN_CODE_ROOT = INV_DES_FLOW_ROOT / "alignn"
MEGNET_PREDICT_SCRIPT = INV_DES_FLOW_ROOT / "pred_formation_energy.py"

DIFFCSP_DATASET_NAME = "mobility2d_highquality280"
DIFFCSP_EXPNAME = "mobility2d_highquality280_ft_v1"

DIFFCSP_PRETRAINED_DIR = MODELS_ROOT / "01_diffcsp_generator" / "pretrained"
DIFFCSP_PRETRAINED_CKPT = DIFFCSP_PRETRAINED_DIR / "PretrainGenerationModel.ckpt"
DIFFCSP_FINETUNED_DIR = (
    MODELS_ROOT / "01_diffcsp_generator" / "finetuned" / "mobility2d_highquality280_ft_v1"
)
DIFFCSP_FINETUNED_CKPT = DIFFCSP_FINETUNED_DIR / "best.ckpt"

ALIGNN_BANDGAP_MODEL_DIR = MODELS_ROOT / "02_alignn_bandgap_nonmetal"
ALIGNN_BANDGAP_CONFIG = ALIGNN_BANDGAP_MODEL_DIR / "config.json"
ALIGNN_BANDGAP_CKPT = ALIGNN_BANDGAP_MODEL_DIR / "last_model.pt"

MEGNET_MODEL_DIR = MODELS_ROOT / "03_megnet_formation_energy"
MEGNET_MODEL_PATH = MEGNET_MODEL_DIR / "FormEGNN-weight.hdf5"
MEGNET_MODEL_CONFIG_PATH = MEGNET_MODEL_DIR / "megnet_formation_energy.hdf5.json"

ALIGNN_MOBILITY_MODEL_DIR = (
    MODELS_ROOT / "04_alignn_mobility" / "mobility_reg_v1_bs8_lr5e4_wu200_nw4"
)
ALIGNN_MOBILITY_MODEL_CONFIG = ALIGNN_MOBILITY_MODEL_DIR / "config.json"
ALIGNN_MOBILITY_MODEL_CKPT = ALIGNN_MOBILITY_MODEL_DIR / "best_model.pt"

CURRENT_FULL_PIPELINE_LINK = RUNS_ROOT / "current__latest_default_semiconductor_pipeline"
DEFAULT_GENERATION_RUN_ID = (
    "20260408__generated_1000_structures__from_mobility2d_highquality280_ft_v1"
)
DEFAULT_GENERATION_RUN_LABEL = "20260408_generated_1000_structures"
DEFAULT_GENERATION_PT_DIR = (
    RUNS_ROOT
    / DEFAULT_GENERATION_RUN_ID
    / "03_generate_structures"
    / "generated_pt"
)
DEFAULT_GENERATION_CIF_DIR = (
    RUNS_ROOT
    / DEFAULT_GENERATION_RUN_ID
    / "03_generate_structures"
    / "generated_cif"
)

STEP01_DIR = STEPS_ROOT / "01_build_dataset"
STEP02_DIR = STEPS_ROOT / "02_finetune_generator"
STEP03_DIR = STEPS_ROOT / "03_generate_structures"
STEP04_DIR = STEPS_ROOT / "04_alignn_bandgap_nonmetal"
STEP05_DIR = STEPS_ROOT / "05_megnet_formation_energy"
STEP05B_DIR = STEPS_ROOT / "05b_phononbench_stability"
STEP06_DIR = STEPS_ROOT / "06_alignn_mobility_rank"
STEP07_DIR = STEPS_ROOT / "07_export_top10_cif"
STEP08_DIR = STEPS_ROOT / "08_orchestration"
