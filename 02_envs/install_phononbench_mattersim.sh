#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${INVDES_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
CODE_ROOT="${ROOT_DIR}/01_code"
MATTERSIM_ROOT="${CODE_ROOT}/MatterSim"
ENV_NAME="mattersim"

if [[ ! -d "${MATTERSIM_ROOT}" ]]; then
  git clone --depth 1 https://github.com/microsoft/mattersim "${MATTERSIM_ROOT}"
fi

pushd "${MATTERSIM_ROOT}" >/dev/null

if command -v mamba >/dev/null 2>&1; then
  if ! mamba env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
    mamba env create -f environment.yaml
  else
    mamba env update -n "${ENV_NAME}" -f environment.yaml
  fi
else
  if ! conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
    conda env create -f environment.yaml
  else
    conda env update -n "${ENV_NAME}" -f environment.yaml
  fi
fi

CONDA_BASE="$(conda info --base)"
# shellcheck disable=SC1091
source "${CONDA_BASE}/etc/profile.d/conda.sh"
conda activate "${ENV_NAME}"

if command -v uv >/dev/null 2>&1; then
  uv pip install -e .
  uv pip install phonopy pymatgen matplotlib pandas ase
else
  pip install -e .
  pip install phonopy pymatgen matplotlib pandas ase
fi

popd >/dev/null

echo "[install_phononbench_mattersim] ready: conda activate ${ENV_NAME}"
