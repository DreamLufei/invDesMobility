# 08 Orchestration

统一入口：

- `run_stage1.sh`
- `run_semiconductor_pipeline.sh`
  默认主路线：生成集自身去重 + 与 `03_datasets/01_source_cif` 参考库去重 + `orthorhombic` + `formation < 0.0 eV/atom` + `PhononBench` 动力学稳定 + `bandgap > 1.0 eV` + 候选 strict90 + mobility 排序 + top10 导出
- `run_dedup_orthorhombic_semiconductor_pipeline.sh`
- `run_orthorhombic_semiconductor_pipeline.sh`
- `run_snap_to_strict90.sh`
- `run_full_pipeline.sh`
- `run_threshold_variants.sh`
- `run_threshold_case.sh`

辅助脚本：

- `deduplicate_cifs_by_structure.py`
- `filter_candidates_by_formation_energy.py`
- `filter_cifs_by_crystal_system.py`
- `link_cifs_from_csv.py`
- `build_mobility_input_from_strict90.py`
- `snap_near_orthorhombic_to_strict90.py`
