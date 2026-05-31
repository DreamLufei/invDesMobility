#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${http_proxy:-}" && -z "${https_proxy:-}" ]]; then
  if timeout 1 bash -lc 'cat < /dev/null > /dev/tcp/127.0.0.1/7890' 2>/dev/null; then
    export http_proxy="http://127.0.0.1:7890"
    export https_proxy="http://127.0.0.1:7890"
    echo "[install_megnet_form] using local proxy ${http_proxy}"
  fi
fi

export PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-120}"

CONDA_BASE="${CONDA_BASE:-$(conda info --base)}"
source "${CONDA_BASE}/etc/profile.d/conda.sh"

ENV_NAME="megnet-form"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INVDES_ROOT="${INVDES_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
ENV_YML="${INVDES_ROOT}/02_envs/megnet-form.yml"

if conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
  echo "[install_megnet_form] conda env ${ENV_NAME} already exists"
else
  conda env create -f "${ENV_YML}"
fi

conda activate "${ENV_NAME}"

python -m pip install --upgrade pip setuptools wheel
python -m pip install tensorflow==2.15.1
python -m pip install megnet==1.3.2 pymatgen==2023.8.10 monty==2023.9.25

python - <<'PY'
import tensorflow as tf
import megnet
import pymatgen
print("tensorflow", tf.__version__)
print("megnet", megnet.__version__)
print("pymatgen", getattr(pymatgen, "__version__", "installed"))
PY

echo "[install_megnet_form] completed"
