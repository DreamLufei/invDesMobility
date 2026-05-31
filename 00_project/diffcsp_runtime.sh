#!/usr/bin/env bash
set -euo pipefail

DIFFCSP_RUNTIME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${DIFFCSP_RUNTIME_DIR}/paths.sh"

STARTUP_DIR="${STEP02_DIR}/python_startup"

if [[ -z "${CONDA_PREFIX:-}" ]]; then
  echo "[_setup_diffcsp_env] CONDA_PREFIX is empty. Activate diffcsp-gen first." >&2
  exit 1
fi

export LD_LIBRARY_PATH="${CONDA_PREFIX}/lib:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="${DIFFCSP_ROOT}:${STARTUP_DIR}:${PYTHONPATH:-}"

if [[ -f "${DIFFCSP_ROOT}/.env" ]]; then
  # Load the repo's runtime paths for hydra and wandb outputs.
  # shellcheck disable=SC1090
  source "${DIFFCSP_ROOT}/.env"
fi

export PROJECT_ROOT="${DIFFCSP_ROOT}"
export HYDRA_JOBS="${LOGS_ROOT}/raw_framework_logs/hydra"
export WABDB_DIR="${LOGS_ROOT}/raw_framework_logs/wandb"

mkdir -p "${LOGS_ROOT}/02_finetune_generator" "${LOGS_ROOT}/03_generate_structures"
mkdir -p "${HYDRA_JOBS}" "${WABDB_DIR}"
