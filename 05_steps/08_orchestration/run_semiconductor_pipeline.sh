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

INPUT_SOURCE_DIR="${INPUT_SOURCE_DIR:-${DEFAULT_GENERATION_CIF_DIR}}"
SOURCE_RUN_NAME_DEFAULT="$(basename "$(dirname "$(dirname "${INPUT_SOURCE_DIR}")")")"
SOURCE_RUN_LABEL="${SOURCE_RUN_LABEL:-${DEFAULT_GENERATION_RUN_LABEL:-${SOURCE_RUN_NAME_DEFAULT}}}"
RUN_NAME="${RUN_NAME:-}"

export INPUT_SOURCE_DIR
export SOURCE_RUN_LABEL
export SOURCE_RUN_ID="${SOURCE_RUN_ID:-${SOURCE_RUN_NAME_DEFAULT}}"
export TARGET_CRYSTAL_SYSTEM="${TARGET_CRYSTAL_SYSTEM:-orthorhombic}"
export DEDUP_REFERENCE_DIR="${DEDUP_REFERENCE_DIR:-${SOURCE_CIF_REFERENCE_ROOT}}"
export DEDUP_BANDGAP_THRESHOLD="${DEDUP_BANDGAP_THRESHOLD:-${BANDGAP_THRESHOLD:-1.0}}"
export DEDUP_FORMATION_ENERGY_THRESHOLD="${DEDUP_FORMATION_ENERGY_THRESHOLD:-${FORMATION_ENERGY_THRESHOLD:-0.0}}"
export TOP_K="${TOP_K:-10}"

if [[ -n "${RUN_NAME}" ]]; then
  export RUN_NAME
fi

bash "${SCRIPT_DIR}/run_dedup_orthorhombic_semiconductor_pipeline.sh"
