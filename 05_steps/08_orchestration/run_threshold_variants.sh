#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT_DIR}/00_project/paths.sh"
if [[ -f "${SCRIPT_DIR}/config.env" ]]; then
  # shellcheck disable=SC1090
  source "${SCRIPT_DIR}/config.env"
fi

RUN_GROUP_ID="${RUN_GROUP_ID:-$(date +%Y%m%d)__three_threshold_cases__from_${DEFAULT_GENERATION_RUN_LABEL}}"
SOURCE_GENERATION_RUN_ID="${SOURCE_GENERATION_RUN_ID:-${DEFAULT_GENERATION_RUN_ID}}"
SOURCE_GENERATION_RUN_LABEL="${SOURCE_GENERATION_RUN_LABEL:-${DEFAULT_GENERATION_RUN_LABEL}}"
TOP_K="${TOP_K:-10}"
ARCHIVE_DIR="${ARCHIVE_ROOT}/old_threshold_experiments/20260409"
RUN_GROUP_LOG_DIR="${LOGS_BY_RUN_ROOT}/${RUN_GROUP_ID}"
ORCH_LOG_PATH="${RUN_GROUP_LOG_DIR}/00_orchestration.log"

mkdir -p "${ARCHIVE_DIR}" "${RUN_GROUP_LOG_DIR}"
exec > >(tee -a "${ORCH_LOG_PATH}") 2>&1

archive_path() {
  local src="$1"
  local name
  local dst
  name="$(basename "${src}")"
  if [[ ! -e "${src}" && ! -L "${src}" ]]; then
    return 0
  fi
  dst="${ARCHIVE_DIR}/${name}"
  if [[ -e "${dst}" || -L "${dst}" ]]; then
    dst="${ARCHIVE_DIR}/${name}__archived_at_$(date +%H%M%S)"
  fi
  mv "${src}" "${dst}"
  echo "[run_threshold_variants] archived ${src} -> ${dst}"
}

echo "[run_threshold_variants] RUN_GROUP_ID=${RUN_GROUP_ID}"
echo "[run_threshold_variants] SOURCE_GENERATION_RUN_ID=${SOURCE_GENERATION_RUN_ID}"

archive_path "${RUNS_ROOT}/20260409_ft1000_threshold_variants"
archive_path "${RUNS_ROOT}/20260409_ft1000_threshold_variants_v2"
rm -f "${RUNS_ROOT}/current_threshold_variants"
if [[ -d "${ARCHIVE_DIR}/20260409_ft1000_threshold_variants_v2" ]]; then
  ln -sfn "${ARCHIVE_DIR}/20260409_ft1000_threshold_variants_v2" "${ARCHIVE_DIR}/current_threshold_variants"
elif [[ -d "${ARCHIVE_DIR}/20260409_ft1000_threshold_variants" ]]; then
  ln -sfn "${ARCHIVE_DIR}/20260409_ft1000_threshold_variants" "${ARCHIVE_DIR}/current_threshold_variants"
fi

RUN_ID_CASE1="20260409__from_${SOURCE_GENERATION_RUN_LABEL}__bg_gt_1p0eV__eform_lt_neg0p5eV_atom__mobility_rank"
RUN_ID_CASE2="20260409__from_${SOURCE_GENERATION_RUN_LABEL}__bg_gt_1p0eV__eform_lt_0p0eV_atom__mobility_rank"
RUN_ID_CASE3="20260409__from_${SOURCE_GENERATION_RUN_LABEL}__bg_gt_0p4eV__eform_lt_neg0p5eV_atom__mobility_rank"

archive_path "${RUNS_ROOT}/${RUN_ID_CASE1}"
archive_path "${RUNS_ROOT}/${RUN_ID_CASE2}"
archive_path "${RUNS_ROOT}/${RUN_ID_CASE3}"

RUN_ID="${RUN_ID_CASE1}" \
SOURCE_GENERATION_RUN_ID="${SOURCE_GENERATION_RUN_ID}" \
CASE_BANDGAP_THRESHOLD="1.0" \
CASE_FORMATION_THRESHOLD="-0.5" \
TOP_K="${TOP_K}" \
bash "${SCRIPT_DIR}/run_threshold_case.sh"

RUN_ID="${RUN_ID_CASE2}" \
SOURCE_GENERATION_RUN_ID="${SOURCE_GENERATION_RUN_ID}" \
CASE_BANDGAP_THRESHOLD="1.0" \
CASE_FORMATION_THRESHOLD="0.0" \
TOP_K="${TOP_K}" \
bash "${SCRIPT_DIR}/run_threshold_case.sh"

RUN_ID="${RUN_ID_CASE3}" \
SOURCE_GENERATION_RUN_ID="${SOURCE_GENERATION_RUN_ID}" \
CASE_BANDGAP_THRESHOLD="0.4" \
CASE_FORMATION_THRESHOLD="-0.5" \
TOP_K="${TOP_K}" \
bash "${SCRIPT_DIR}/run_threshold_case.sh"

echo "[run_threshold_variants] completed"
echo "[run_threshold_variants] case_1=${RUNS_ROOT}/${RUN_ID_CASE1}"
echo "[run_threshold_variants] case_2=${RUNS_ROOT}/${RUN_ID_CASE2}"
echo "[run_threshold_variants] case_3=${RUNS_ROOT}/${RUN_ID_CASE3}"
