#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${http_proxy:-}" && -z "${https_proxy:-}" ]]; then
  if timeout 1 bash -lc 'cat < /dev/null > /dev/tcp/127.0.0.1/7890' 2>/dev/null; then
    export http_proxy="http://127.0.0.1:7890"
    export https_proxy="http://127.0.0.1:7890"
    echo "[install_alignn_screen] using local proxy ${http_proxy}"
  fi
fi

export PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-120}"

CONDA_BASE="${CONDA_BASE:-$(conda info --base)}"
source "${CONDA_BASE}/etc/profile.d/conda.sh"

ENV_NAME="alignn-screen"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INVDES_ROOT="${INVDES_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
ENV_YML="${INVDES_ROOT}/02_envs/alignn-screen.yml"
ALIGNN_ROOT="${INVDES_ROOT}/01_code/InvDesFlow/alignn"
PATCH_DGL_SCRIPT="${INVDES_ROOT}/05_steps/06_alignn_mobility_rank/patch_dgl_graphbolt.py"

if conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
  echo "[install_alignn_screen] conda env ${ENV_NAME} already exists"
else
  conda env create -f "${ENV_YML}"
fi

conda activate "${ENV_NAME}"

python -m pip install --upgrade pip setuptools wheel
python -m pip install torch==2.4.1
python -m pip install --force-reinstall --no-deps torchdata==0.8.0
python -m pip install --force-reinstall --no-deps "dgl==2.4.0+cu121" \
  -f "https://data.dgl.ai/wheels/torch-2.4/cu121/repo.html"
python -m pip install pyyaml
python -m pip install -e "${ALIGNN_ROOT}"
python "${PATCH_DGL_SCRIPT}"

export DGLBACKEND=pytorch
export DGL_SKIP_GRAPHBOLT=1
python - <<'PY'
import torch
import dgl
import alignn
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
print("dgl", dgl.__version__)
g = dgl.graph(([0, 1], [1, 2]))
g = g.to("cuda")
print("dgl cuda graph ok", g.device)
print("alignn import ok")
PY

echo "[install_alignn_screen] completed"
