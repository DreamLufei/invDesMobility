# 05B PhononBench Stability

作用：对形成能筛后的候选做 MatterSim/PhononBench 声子稳定性判断，只保留动力学稳定结构。

输入：某次 run 的 `05_candidates_after_formation/formation_selected_cif`

输出：某次 run 的 `06_phononbench_stability/`

- `phonopy_inputs/`: Phonopy 输入文件
- `phonon_output/`: 声子计算中间结果
- `relaxed/`: 弛豫后结构与 `Lable.txt`
- `phonon_stability_all.csv`: 全部样本稳定性汇总
- `phonon_stable_candidates.csv`: 动力学稳定候选
- `stable_relaxed_cif/`: 供后续带隙筛选使用的稳定弛豫 CIF

主入口：`run.sh`
