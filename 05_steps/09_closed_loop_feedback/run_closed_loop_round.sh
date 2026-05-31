#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT_DIR}/00_project/paths.sh"

ROUND_INDEX="${ROUND_INDEX:-}"
ROUND_ID="${ROUND_ID:-}"
PARENT_ROUND_ID="${PARENT_ROUND_ID:-round_00_bootstrap}"
FEEDBACK_SOURCE_ROUND_ID="${FEEDBACK_SOURCE_ROUND_ID:-${PARENT_ROUND_ID}}"
FEEDBACK_BATCH_ROOT="${FEEDBACK_BATCH_ROOT:-}"
MONGO_URI="${MONGO_URI:-}"
MONGO_DB="${MONGO_DB:-materials_database}"
MONGO_COLLECTION="${MONGO_COLLECTION:-Vertical_NM_Sample_20}"
TOTAL_SAMPLES="${TOTAL_SAMPLES:-100000}"
SAMPLES_PER_JOB="${SAMPLES_PER_JOB:-1000}"
NUM_BATCHES_TO_SAMPLES="${NUM_BATCHES_TO_SAMPLES:-1}"
TOP_K="${TOP_K:-10}"
GPU_LIST="${GPU_LIST:-0,1,2,3}"
PUBLISH_DRY_RUN="${PUBLISH_DRY_RUN:-0}"
DOWNSTREAM_DRY_RUN="${DOWNSTREAM_DRY_RUN:-0}"
SKIP_DOWNSTREAM_RUN="${SKIP_DOWNSTREAM_RUN:-0}"
DOWNSTREAM_RUNS_ROOT="${DOWNSTREAM_RUNS_ROOT:-}"
TWO_D_MOBILITY_ROOT="${TWO_D_MOBILITY_ROOT:-$(cd "${ROOT_DIR}/.." && pwd)/2d-mobility}"
FEEDBACK_WEIGHT="${FEEDBACK_WEIGHT:-12}"
MIN_TRAIN_ROWS="${MIN_TRAIN_ROWS:-10000}"
DIFFCSP_LR_LOG_DIR="${LOGS_ROOT}/02_finetune_generator"
ALIGNN_LOG_DIR="${LOGS_ROOT}/06_alignn_mobility_rank"
FEEDBACK_ARCHIVE_ROOT="${METADATA_DIR}/05_closed_loop_feedback"

if [[ -z "${ROUND_INDEX}" ]]; then
  echo "[run_closed_loop_round] ROUND_INDEX is required" >&2
  exit 2
fi
if [[ -z "${ROUND_ID}" ]]; then
  echo "[run_closed_loop_round] ROUND_ID is required" >&2
  exit 2
fi
if [[ -z "${FEEDBACK_BATCH_ROOT}" ]]; then
  echo "[run_closed_loop_round] FEEDBACK_BATCH_ROOT is required" >&2
  exit 2
fi
if [[ -z "${MONGO_URI}" ]]; then
  echo "[run_closed_loop_round] MONGO_URI is required" >&2
  exit 2
fi

ROUND_SUFFIX="$(printf '%02d' "${ROUND_INDEX}")"
GENERATOR_MODEL_ID="${GENERATOR_MODEL_ID:-generator_round_${ROUND_SUFFIX}}"
ALIGNN_MODEL_ID="${ALIGNN_MODEL_ID:-alignn_mobility_round_${ROUND_SUFFIX}}"
DIFFCSP_ROUND_DATASET_NAME="${DIFFCSP_ROUND_DATASET_NAME:-mobility2d_feedback_round_${ROUND_SUFFIX}}"
ALIGNN_ROUND_DATASET_DIR="${ALIGNN_ROUND_DATASET_DIR:-${DATASETS_ROOT}/03_alignn_mobility_dataset/round_${ROUND_SUFFIX}}"
GENERATOR_ROUND_DIR="${GENERATOR_ROUND_DIR:-${MODELS_ROOT}/01_diffcsp_generator/finetuned/${GENERATOR_MODEL_ID}}"
ALIGNN_ROUND_DIR="${ALIGNN_ROUND_DIR:-${MODELS_ROOT}/04_alignn_mobility/${ALIGNN_MODEL_ID}}"
ROUND_RUN_NAME="${ROUND_RUN_NAME:-${ROUND_ID}__closed_loop_round}"
ROUND_ROOT="${RUNS_ROOT}/${ROUND_RUN_NAME}"
ROUND_LOG_DIR="${LOGS_BY_RUN_ROOT}/${ROUND_RUN_NAME}"
LOOP_LOG_PATH="${ROUND_LOG_DIR}/00_closed_loop.log"
FEEDBACK_DIR="${ROUND_ROOT}/01_trusted_feedback"
ALIGNN_DATA_MANIFEST="${ROUND_ROOT}/02_alignn_round_dataset_manifest.json"
ALIGNN_TRAIN_MANIFEST="${ROUND_ROOT}/03_alignn_round_train_manifest.json"
DIFFCSP_DATASET_MANIFEST="${ROUND_ROOT}/04_diffcsp_round_dataset_manifest.json"
GENERATOR_TRAIN_MANIFEST="${ROUND_ROOT}/05_generator_round_train_manifest.json"
FEEDBACK_ARCHIVE_DIR="${FEEDBACK_ARCHIVE_ROOT}/${FEEDBACK_SOURCE_ROUND_ID}"
FEEDBACK_SNAPSHOT_ID="${FEEDBACK_SNAPSHOT_ID:-feedback_snapshot_up_to_${FEEDBACK_SOURCE_ROUND_ID}}"
GENERATION_RUN_ID="${GENERATION_RUN_ID:-${ROUND_ID}__generated_${TOTAL_SAMPLES}_structures__from_${GENERATOR_MODEL_ID}}"
PIPELINE_RUN_NAME="${PIPELINE_RUN_NAME:-${ROUND_ID}__screen_from_${GENERATION_RUN_ID}}"
PUBLISH_MANIFEST_PATH="${ROUND_ROOT}/08_publish_manifest.json"
LOOP_MANIFEST_PATH="${ROUND_ROOT}/loop_manifest.json"
BATCH_TAG="${BATCH_TAG:-${ROUND_ID}__mobility_batch}"
if [[ -z "${DOWNSTREAM_RUNS_ROOT}" ]]; then
  DOWNSTREAM_RUNS_ROOT="${ROUND_ROOT}/09_2d_mobility_batch"
fi

mkdir -p "${ROUND_ROOT}" "${ROUND_LOG_DIR}" "${FEEDBACK_ARCHIVE_ROOT}" "${ALIGNN_ROUND_DATASET_DIR}" "${GENERATOR_ROUND_DIR}" "${ALIGNN_ROUND_DIR}"
exec > >(tee -a "${LOOP_LOG_PATH}") 2>&1

PREV_ROUND_SUFFIX="$(printf '%02d' "$((ROUND_INDEX - 1))")"
DEFAULT_PREV_GENERATOR_CKPT="${MODELS_ROOT}/01_diffcsp_generator/finetuned/generator_round_${PREV_ROUND_SUFFIX}/best.ckpt"
DEFAULT_PREV_ALIGNN_CKPT="${MODELS_ROOT}/04_alignn_mobility/alignn_mobility_round_${PREV_ROUND_SUFFIX}/best_model.pt"
if [[ -f "${DEFAULT_PREV_GENERATOR_CKPT}" ]]; then
  GENERATOR_WARM_START_CKPT_DEFAULT="${DEFAULT_PREV_GENERATOR_CKPT}"
else
  GENERATOR_WARM_START_CKPT_DEFAULT="${DIFFCSP_FINETUNED_CKPT}"
fi
if [[ -f "${DEFAULT_PREV_ALIGNN_CKPT}" ]]; then
  ALIGNN_RESTART_MODEL_DEFAULT="${DEFAULT_PREV_ALIGNN_CKPT}"
else
  ALIGNN_RESTART_MODEL_DEFAULT="${ALIGNN_MOBILITY_MODEL_CKPT}"
fi
GENERATOR_WARM_START_CKPT="${GENERATOR_WARM_START_CKPT:-${GENERATOR_WARM_START_CKPT_DEFAULT}}"
ALIGNN_RESTART_MODEL_PATH="${ALIGNN_RESTART_MODEL_PATH:-${ALIGNN_RESTART_MODEL_DEFAULT}}"
ALIGNN_CONFIG_PATH="${ALIGNN_CONFIG_PATH:-${ALIGNN_MOBILITY_MODEL_CONFIG}}"

mapfile -t HISTORICAL_FEEDBACK_CSVS < <(find "${FEEDBACK_ARCHIVE_ROOT}" -mindepth 2 -maxdepth 2 -name 'trusted_materials.csv' | sort)

echo "[run_closed_loop_round] step 01: extract trusted feedback from ${FEEDBACK_BATCH_ROOT}"
python "${SCRIPT_DIR}/extract_trusted_feedback.py" \
  --batch-root "${FEEDBACK_BATCH_ROOT}" \
  --output-dir "${FEEDBACK_DIR}" \
  --round-id "${FEEDBACK_SOURCE_ROUND_ID}" \
  --batch-id "$(basename "${FEEDBACK_BATCH_ROOT}")"

rm -rf "${FEEDBACK_ARCHIVE_DIR}"
mkdir -p "${FEEDBACK_ARCHIVE_DIR}"
cp -f "${FEEDBACK_DIR}/trusted_channels.csv" "${FEEDBACK_ARCHIVE_DIR}/trusted_channels.csv"
cp -f "${FEEDBACK_DIR}/trusted_materials.csv" "${FEEDBACK_ARCHIVE_DIR}/trusted_materials.csv"
cp -f "${FEEDBACK_DIR}/rejected_feedback.csv" "${FEEDBACK_ARCHIVE_DIR}/rejected_feedback.csv"
cp -f "${FEEDBACK_DIR}/feedback_summary.json" "${FEEDBACK_ARCHIVE_DIR}/feedback_summary.json"
mkdir -p "${FEEDBACK_ARCHIVE_DIR}/trusted_relaxed_cif"
find "${FEEDBACK_ARCHIVE_DIR}/trusted_relaxed_cif" -mindepth 1 -maxdepth 1 -type f -delete 2>/dev/null || true
cp -f "${FEEDBACK_DIR}/trusted_relaxed_cif/"*.cif "${FEEDBACK_ARCHIVE_DIR}/trusted_relaxed_cif/" 2>/dev/null || true

mapfile -t HISTORICAL_FEEDBACK_CSVS < <(find "${FEEDBACK_ARCHIVE_ROOT}" -mindepth 2 -maxdepth 2 -name 'trusted_materials.csv' | sort)
if [[ "${#HISTORICAL_FEEDBACK_CSVS[@]}" -eq 0 ]]; then
  echo "[run_closed_loop_round] no trusted feedback CSVs found after extraction" >&2
  exit 2
fi

echo "[run_closed_loop_round] step 02: build ALIGNN round dataset"
ALIGNN_DATASET_CMD=(
  python "${SCRIPT_DIR}/build_alignn_round_dataset.py"
  --output-dir "${ALIGNN_ROUND_DATASET_DIR}"
  --manifest-path "${ALIGNN_DATA_MANIFEST}"
  --base-cif-dir "${SOURCE_CIF_DIR}"
  --base-labels "${SOURCE_CIF_DIR}/id_prop.csv"
)
for feedback_csv in "${HISTORICAL_FEEDBACK_CSVS[@]}"; do
  ALIGNN_DATASET_CMD+=(--feedback-csv "${feedback_csv}")
done
"${ALIGNN_DATASET_CMD[@]}"

echo "[run_closed_loop_round] step 03: fine-tune ALIGNN mobility model"
ALIGNN_MOBILITY_SKIP_PREPARE=1 \
ALIGNN_MOBILITY_DATA_DIR_OVERRIDE="${ALIGNN_ROUND_DATASET_DIR}" \
ALIGNN_MOBILITY_OUTPUT_DIR="${ALIGNN_ROUND_DIR}" \
ALIGNN_MOBILITY_CONFIG_OVERRIDE="${ALIGNN_CONFIG_PATH}" \
ALIGNN_MOBILITY_RESTART_MODEL_PATH="${ALIGNN_RESTART_MODEL_PATH}" \
ALIGNN_MOBILITY_PREPARE_LOG_PATH="${ALIGNN_LOG_DIR}/${ALIGNN_MODEL_ID}__prepare.log" \
ALIGNN_MOBILITY_PATCH_LOG_PATH="${ALIGNN_LOG_DIR}/${ALIGNN_MODEL_ID}__patch_dgl.log" \
ALIGNN_MOBILITY_TRAIN_LOG_PATH="${ALIGNN_LOG_DIR}/${ALIGNN_MODEL_ID}.log" \
bash "${STEP06_DIR}/train_best.sh"

if [[ ! -f "${ALIGNN_ROUND_DIR}/best_model.pt" ]]; then
  echo "[run_closed_loop_round] missing ALIGNN checkpoint: ${ALIGNN_ROUND_DIR}/best_model.pt" >&2
  exit 2
fi

echo "[run_closed_loop_round] step 04: build DiffCSP round dataset"
DIFFCSP_DATASET_CMD=(
  python "${SCRIPT_DIR}/build_diffcsp_round_dataset.py"
  --dataset-name "${DIFFCSP_ROUND_DATASET_NAME}"
  --manifest-path "${DIFFCSP_DATASET_MANIFEST}"
  --base-cif-dir "${SOURCE_CIF_DIR}"
  --feedback-weight "${FEEDBACK_WEIGHT}"
  --min-train-rows "${MIN_TRAIN_ROWS}"
)
for feedback_csv in "${HISTORICAL_FEEDBACK_CSVS[@]}"; do
  DIFFCSP_DATASET_CMD+=(--feedback-csv "${feedback_csv}")
done
"${DIFFCSP_DATASET_CMD[@]}"

echo "[run_closed_loop_round] step 05: fine-tune generator model"
DATASET_NAME="${DIFFCSP_ROUND_DATASET_NAME}" \
CKPT_PATH="${GENERATOR_WARM_START_CKPT}" \
EXP_NAME="${GENERATOR_MODEL_ID}" \
FINETUNED_DIR="${GENERATOR_ROUND_DIR}" \
REPORT_PATH="${DIFFCSP_LR_LOG_DIR}/${GENERATOR_MODEL_ID}_ckpt_compat.json" \
FILTERED_CKPT_PATH="${DIFFCSP_LR_LOG_DIR}/${GENERATOR_MODEL_ID}_filtered.ckpt" \
LOG_PATH="${DIFFCSP_LR_LOG_DIR}/${GENERATOR_MODEL_ID}.log" \
bash "${STEP02_DIR}/run.sh"

if [[ ! -f "${GENERATOR_ROUND_DIR}/best.ckpt" ]]; then
  echo "[run_closed_loop_round] missing generator checkpoint: ${GENERATOR_ROUND_DIR}/best.ckpt" >&2
  exit 2
fi

echo "[run_closed_loop_round] step 06: generate ${TOTAL_SAMPLES} structures"
MODEL_PATH="${GENERATOR_ROUND_DIR}" \
RUN_ID="${GENERATION_RUN_ID}" \
TOTAL_SAMPLES="${TOTAL_SAMPLES}" \
SAMPLES_PER_JOB="${SAMPLES_PER_JOB}" \
NUM_BATCHES_TO_SAMPLES="${NUM_BATCHES_TO_SAMPLES}" \
GPU_LIST="${GPU_LIST}" \
LABEL_PREFIX="${ROUND_ID}" \
bash "${STEP03_DIR}/run_multigpu.sh"

GENERATION_CIF_DIR="${RUNS_ROOT}/${GENERATION_RUN_ID}/03_generate_structures/generated_cif"
if [[ ! -d "${GENERATION_CIF_DIR}" ]]; then
  echo "[run_closed_loop_round] missing generated CIF dir: ${GENERATION_CIF_DIR}" >&2
  exit 2
fi

echo "[run_closed_loop_round] step 07: screening pipeline"
INPUT_SOURCE_DIR="${GENERATION_CIF_DIR}" \
SOURCE_RUN_LABEL="${GENERATION_RUN_ID}" \
SOURCE_RUN_ID="${GENERATION_RUN_ID}" \
RUN_NAME="${PIPELINE_RUN_NAME}" \
TOP_K="${TOP_K}" \
ALIGNN_MOBILITY_MODEL_CONFIG_OVERRIDE="${ALIGNN_ROUND_DIR}/config.json" \
ALIGNN_MOBILITY_MODEL_CKPT_OVERRIDE="${ALIGNN_ROUND_DIR}/best_model.pt" \
bash "${STEP08_DIR}/run_dedup_orthorhombic_semiconductor_pipeline.sh"

PIPELINE_RUN_ROOT="${RUNS_ROOT}/${PIPELINE_RUN_NAME}"
STRICT90_CSV="$(find "${PIPELINE_RUN_ROOT}" -maxdepth 2 -type f -name '*_candidates_strict90.csv' | sort | tail -n 1)"
if [[ -z "${STRICT90_CSV}" ]]; then
  echo "[run_closed_loop_round] missing strict90 merged CSV under ${PIPELINE_RUN_ROOT}" >&2
  exit 2
fi

echo "[run_closed_loop_round] step 08: publish strict90 survivors to Mongo"
PUBLISH_ARGS=(
  python "${SCRIPT_DIR}/publish_round_candidates_to_mongo.py"
  --strict90-csv "${STRICT90_CSV}"
  --output-manifest "${PUBLISH_MANIFEST_PATH}"
  --mongo-uri "${MONGO_URI}"
  --mongo-db "${MONGO_DB}"
  --mongo-collection "${MONGO_COLLECTION}"
  --round-index "${ROUND_INDEX}"
  --round-id "${ROUND_ID}"
  --parent-round-id "${PARENT_ROUND_ID}"
  --generator-model-id "${GENERATOR_MODEL_ID}"
  --alignn-model-id "${ALIGNN_MODEL_ID}"
  --feedback-snapshot-id "${FEEDBACK_SNAPSHOT_ID}"
  --pipeline-run-id "${PIPELINE_RUN_NAME}"
)
if [[ "${PUBLISH_DRY_RUN}" == "1" ]]; then
  PUBLISH_ARGS+=(--dry-run)
fi
"${PUBLISH_ARGS[@]}"

PUBLISHABLE_COUNT="$(python - "${PUBLISH_MANIFEST_PATH}" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
print(payload.get('counts', {}).get('publishable_rows', 0))
PY
)"

if [[ "${PUBLISHABLE_COUNT}" == "0" ]]; then
  echo "[run_closed_loop_round] no strict90 survivors to submit; skipping downstream batch"
elif [[ "${SKIP_DOWNSTREAM_RUN}" == "1" ]]; then
  echo "[run_closed_loop_round] downstream batch skipped by SKIP_DOWNSTREAM_RUN=1"
else
  echo "[run_closed_loop_round] step 09: run 2d-mobility batch for ${ROUND_ID}"
  CLAIM_FILTER_JSON="{\"loop_metadata.round_id\": \"${ROUND_ID}\"}"
  DOWNSTREAM_ARGS=(python "${TWO_D_MOBILITY_ROOT}/run_mongo_batch.py" --fresh-materials)
  if [[ "${DOWNSTREAM_DRY_RUN}" == "1" ]]; then
    DOWNSTREAM_ARGS+=(--dry-run)
  fi
  MONGO_URI="${MONGO_URI}" \
  MONGO_DB="${MONGO_DB}" \
  MONGO_COLLECTION="${MONGO_COLLECTION}" \
  BATCH_TAG="${BATCH_TAG}" \
  RUNS_ROOT="${DOWNSTREAM_RUNS_ROOT}" \
  MONGO_CLAIM_FILTER_JSON="${CLAIM_FILTER_JSON}" \
  "${DOWNSTREAM_ARGS[@]}"
fi

echo "[run_closed_loop_round] writing loop manifest"
python - "${LOOP_MANIFEST_PATH}" "${ROUND_ID}" "${ROUND_INDEX}" "${PARENT_ROUND_ID}" "${FEEDBACK_SOURCE_ROUND_ID}" "${FEEDBACK_DIR}/feedback_summary.json" "${ALIGNN_DATA_MANIFEST}" "${DIFFCSP_DATASET_MANIFEST}" "${PUBLISH_MANIFEST_PATH}" "${PIPELINE_RUN_ROOT}/manifest.json" "${GENERATOR_MODEL_ID}" "${GENERATOR_ROUND_DIR}" "${ALIGNN_MODEL_ID}" "${ALIGNN_ROUND_DIR}" "${GENERATION_RUN_ID}" "${PIPELINE_RUN_NAME}" "${BATCH_TAG}" "${MONGO_COLLECTION}" "${DOWNSTREAM_RUNS_ROOT}" <<'PY'
import json
import sys
from pathlib import Path


def read_json(path_str):
    path = Path(path_str)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))

payload = {
    'round_id': sys.argv[2],
    'round_index': int(sys.argv[3]),
    'parent_round_id': sys.argv[4],
    'feedback_source_round_id': sys.argv[5],
    'feedback_summary': read_json(sys.argv[6]),
    'alignn_dataset_manifest': read_json(sys.argv[7]),
    'diffcsp_dataset_manifest': read_json(sys.argv[8]),
    'publish_manifest': read_json(sys.argv[9]),
    'screening_manifest': read_json(sys.argv[10]),
    'generator_model': {
        'model_id': sys.argv[11],
        'model_dir': sys.argv[12],
    },
    'alignn_model': {
        'model_id': sys.argv[13],
        'model_dir': sys.argv[14],
    },
    'generation_run_id': sys.argv[15],
    'pipeline_run_id': sys.argv[16],
    'downstream_batch_tag': sys.argv[17],
    'mongo_collection': sys.argv[18],
    'downstream_runs_root': sys.argv[19],
}
path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps(payload, indent=2, ensure_ascii=False))
PY

echo "[run_closed_loop_round] completed: ${ROUND_ROOT}"
