import os
import csv
import time
from pathlib import Path
import sys
import torch
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "00_project"))

from paths import (  # noqa: E402
    ALIGNN_CODE_ROOT,
    ALIGNN_BANDGAP_CKPT,
    ALIGNN_BANDGAP_CONFIG,
    DEFAULT_GENERATION_CIF_DIR,
    RUNS_ROOT,
)

sys.path.insert(0, str(ALIGNN_CODE_ROOT))

from jarvis.db.jsonutils import loadjson  # noqa: E402
from jarvis.core.atoms import Atoms  # noqa: E402
from alignn.models.alignn_atomwise import ALIGNNAtomWise, ALIGNNAtomWiseConfig  # noqa: E402
from alignn.graphs import Graph  # noqa: E402

# =========================
# 模型配置路径（请根据实际修改）
# =========================
CONFIG_PATH = os.environ.get(
    "ALIGNN_BANDGAP_CONFIG",
    str(ALIGNN_BANDGAP_CONFIG),
)
CHECKPOINT_PATH = os.environ.get(
    "ALIGNN_BANDGAP_CHECKPOINT",
    str(ALIGNN_BANDGAP_CKPT),
)
INPUT_CIF_DIR = os.environ.get(
    "ALIGNN_CIF_INPUT_DIR",
    str(DEFAULT_GENERATION_CIF_DIR),
)
OUTPUT_CSV = os.environ.get(
    "ALIGNN_BANDGAP_OUTPUT_CSV",
    str(RUNS_ROOT / "adhoc_bandgap_screen" / "02_alignn_bandgap_nonmetal" / "bandgap_predictions.csv"),
)
NONMETAL_CSV = os.environ.get(
    "ALIGNN_NONMETAL_OUTPUT_CSV",
    str(RUNS_ROOT / "adhoc_bandgap_screen" / "02_alignn_bandgap_nonmetal" / "nonmetal_candidates.csv"),
)
BANDGAP_THRESHOLD = float(os.environ.get("ALIGNN_BANDGAP_THRESHOLD", "0.4"))
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
CUTOFF = 8
MAX_NEIGHBORS = 20

# =========================
# 待预测的文件夹字典（模型名称 -> CIF所在目录）
# =========================
relaxed_paths = {
    "mobility2d_highquality280_gen": INPUT_CIF_DIR,
}

# =========================
# 输出CSV文件
# =========================
os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
os.makedirs(os.path.dirname(NONMETAL_CSV), exist_ok=True)

# =========================
# 加载ALIGNN模型
# =========================
def load_alignn_model(config_path, checkpoint_path, device):
    """加载ALIGNN原子属性模型"""
    rest_config = loadjson(config_path)
    tmp = ALIGNNAtomWiseConfig(**rest_config["model"])
    model = ALIGNNAtomWise(tmp)
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    model.load_state_dict(checkpoint)
    model = model.to(device)
    model.eval()
    return model

if not os.path.exists(CONFIG_PATH):
    raise FileNotFoundError(f"Missing ALIGNN config file: {CONFIG_PATH}")

if not os.path.exists(CHECKPOINT_PATH):
    raise FileNotFoundError(f"Missing ALIGNN checkpoint file: {CHECKPOINT_PATH}")

if not os.path.isdir(INPUT_CIF_DIR):
    raise FileNotFoundError(f"Missing CIF input directory: {INPUT_CIF_DIR}")

print("Loading ALIGNN model...")
model = load_alignn_model(CONFIG_PATH, CHECKPOINT_PATH, DEVICE)
print("Model loaded.")

# =========================
# 单个CIF预测函数
# =========================
def predict_bandgap(cif_path, model, device):
    """输入CIF路径，返回带隙预测值（若失败则返回None）"""
    try:
        atoms = Atoms.from_cif(cif_path, use_cif2cell=False)
        g, lg = Graph.atom_dgl_multigraph(
            atoms,
            cutoff=CUTOFF,
            max_neighbors=MAX_NEIGHBORS,
        )
        with torch.no_grad():
            out = model([g.to(device), lg.to(device)])["out"]
        # 模型输出为列表，取第一个值作为带隙
        bandgap = out.cpu().numpy().flatten()[0]
        return bandgap
    except Exception as e:
        print(f"Error processing {cif_path}: {e}")
        return None

# =========================
# 读取已处理文件（避免重复）
# =========================
done_cifs = set()
if os.path.exists(OUTPUT_CSV):
    df_done = pd.read_csv(OUTPUT_CSV)
    done_cifs = set(df_done["cif_path"].tolist())
    print(f"Found {len(done_cifs)} CIFs already processed. Skipping them.")

# =========================
# 构建待处理任务列表
# =========================
tasks = []  # 每个元素为 (model_key, cif_path)
for model_key, relaxed_dir in relaxed_paths.items():
    for root, dirs, files in os.walk(relaxed_dir):
        for file in files:
            if file.endswith(".cif"):
                full_path = os.path.join(root, file)
                if full_path not in done_cifs:
                    tasks.append((model_key, full_path))
print(f"Total CIF files to process in this run: {len(tasks)}")

# =========================
# 分批预测并写入CSV
# =========================
def save_csv_batch(path, data_list, header=False):
    with open(path, "a", newline="") as csv_file:
        writer = csv.writer(csv_file)
        if header:
            writer.writerow(["model", "cif_path", "cif_name", "bandgap", "is_nonmetal"])
        writer.writerows(data_list)
    print(f"Saved batch of {len(data_list)} rows to {path}")


def write_empty_outputs():
    empty_columns = ["model", "cif_path", "cif_name", "bandgap", "is_nonmetal"]
    pd.DataFrame(columns=empty_columns).to_csv(OUTPUT_CSV, index=False)
    pd.DataFrame(columns=empty_columns).to_csv(NONMETAL_CSV, index=False)
    print(
        f"No CIF tasks found. Wrote empty outputs to {OUTPUT_CSV} and {NONMETAL_CSV}"
    )


if not tasks:
    write_empty_outputs()
    raise SystemExit(0)

BATCH_SIZE = 50
start_time = time.time()

for batch_start in range(0, len(tasks), BATCH_SIZE):
    batch_tasks = tasks[batch_start : batch_start + BATCH_SIZE]
    batch_results = []
    for model_key, cif_path in batch_tasks:
        cif_name = os.path.basename(cif_path)
        bandgap = predict_bandgap(cif_path, model, DEVICE)
        is_nonmetal = False
        if bandgap is None:
            bandgap = "NA"   # 预测失败标记
        else:
            is_nonmetal = float(bandgap) > BANDGAP_THRESHOLD
        batch_results.append([model_key, cif_path, cif_name, bandgap, is_nonmetal])
        print(f"{cif_name} -> {bandgap} -> nonmetal={is_nonmetal}")

    # 写入CSV（首批且CSV原本不存在时才写入表头）
    header = (batch_start == 0 and not os.path.exists(OUTPUT_CSV))
    save_csv_batch(OUTPUT_CSV, batch_results, header=header)
    print(f"Batch {batch_start // BATCH_SIZE + 1} processed, {len(batch_results)} files.")

end_time = time.time()
print(f"Total time: {end_time - start_time:.2f} s")

df_result = pd.read_csv(OUTPUT_CSV)
df_result["bandgap_numeric"] = pd.to_numeric(df_result["bandgap"], errors="coerce")
df_nonmetal = df_result[df_result["bandgap_numeric"] > BANDGAP_THRESHOLD].copy()
df_nonmetal.to_csv(NONMETAL_CSV, index=False)
print(
    f"Nonmetal threshold={BANDGAP_THRESHOLD:.3f} eV, "
    f"{len(df_nonmetal)} candidates saved to {NONMETAL_CSV}"
)
