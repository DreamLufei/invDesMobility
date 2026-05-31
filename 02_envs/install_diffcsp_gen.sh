#!/usr/bin/env bash
set -euo pipefail

CONDA_BASE="${CONDA_BASE:-$(conda info --base)}"
source "${CONDA_BASE}/etc/profile.d/conda.sh"

ENV_NAME="diffcsp-gen"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INVDES_ROOT="${INVDES_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
ENV_YML="${INVDES_ROOT}/02_envs/diffcsp-gen.yml"
REPO_ROOT="${INVDES_ROOT}/01_code/InvDesFlow/DiffCSP"

if conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
  echo "[install_diffcsp_gen] conda env ${ENV_NAME} already exists"
else
  conda env create -f "${ENV_YML}"
fi

conda activate "${ENV_NAME}"

python -m pip install --upgrade pip setuptools wheel

python -m pip install \
  torch==1.9.0+cu111 \
  torchvision==0.10.0+cu111 \
  torchaudio==0.9.0 \
  -f https://download.pytorch.org/whl/torch_stable.html

python -m pip install \
  torch-scatter==2.0.8 \
  torch-sparse==0.6.12 \
  torch-cluster==1.5.9 \
  torch-spline-conv==1.2.1 \
  -f https://data.pyg.org/whl/torch-1.9.0+cu111.html

python -m pip install \
  torch-geometric==1.7.2 \
  pytorch-lightning==1.3.8 \
  torchmetrics==0.6.0 \
  hydra-core==1.1.0 \
  omegaconf==2.1.1 \
  python-dotenv==1.0.1 \
  numpy==1.23.5 \
  pandas==1.5.3 \
  scipy==1.10.1 \
  scikit-learn==1.1.3 \
  networkx==2.8.8 \
  pymatgen==2023.8.10 \
  pyxtal==0.5.5 \
  smact==2.5.5 \
  p_tqdm==1.4.2 \
  pathos==0.3.2 \
  chemparse==0.3.2 \
  einops==0.6.1 \
  tqdm==4.66.5 \
  wandb==0.12.21 \
  matplotlib==3.7.5 \
  ase==3.23.0 \
  sympy==1.12 \
  pyparsing==2.4.7

export LD_LIBRARY_PATH="${CONDA_PREFIX}/lib:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"

python - <<'PY'
import torch
import pytorch_lightning
import hydra
import pymatgen
import torch_geometric
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
print("pytorch_lightning", pytorch_lightning.__version__)
print("hydra", hydra.__version__)
print("pymatgen", pymatgen.__version__)
print("torch_geometric", torch_geometric.__version__)
PY

echo "[install_diffcsp_gen] completed"
