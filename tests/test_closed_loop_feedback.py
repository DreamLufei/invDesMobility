from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from pymatgen.core import Lattice, Structure
from pymatgen.io.cif import CifWriter
from pymatgen.io.vasp import Poscar

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "05_steps" / "09_closed_loop_feedback"
ORCH_DIR = ROOT / "05_steps" / "08_orchestration"
DATA_ROOT = ROOT / "01_code" / "InvDesFlow" / "data"

sys.path.insert(0, str(SCRIPT_DIR))

from closed_loop_common import trusted_channel_rows_for_material  # noqa: E402


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class ClosedLoopFeedbackTests(unittest.TestCase):
    def _write_structure(self, path: Path) -> Structure:
        structure = Structure(
            lattice=Lattice.orthorhombic(3.2, 4.1, 18.0),
            species=["Si", "Si"],
            coords=[[0.1, 0.2, 0.3], [0.6, 0.7, 0.3]],
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".cif":
            CifWriter(structure).write_file(str(path))
        else:
            Poscar(structure).write_file(str(path))
        return structure

    def _write_shifted_structure(self, path: Path) -> Structure:
        structure = Structure(
            lattice=Lattice.orthorhombic(3.5, 4.4, 18.5),
            species=["Si", "P"],
            coords=[[0.15, 0.25, 0.32], [0.55, 0.68, 0.28]],
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".cif":
            CifWriter(structure).write_file(str(path))
        else:
            Poscar(structure).write_file(str(path))
        return structure

    def test_dedup_screening_script_keeps_external_top_k_over_config_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            existing_run_root = tmp / "existing_run"
            existing_run_root.mkdir()
            env = dict(os.environ)
            env.update(
                {
                    "TOP_K": "30",
                    "RUN_ROOT": str(existing_run_root),
                    "INPUT_SOURCE_DIR": str(tmp / "missing_input"),
                }
            )

            result = subprocess.run(
                ["bash", "-x", str(ORCH_DIR / "run_dedup_orthorhombic_semiconductor_pipeline.sh")],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("TOPK_TOKEN=top30", result.stderr)
        self.assertNotIn("TOPK_TOKEN=top10", result.stderr)

    def test_trusted_feedback_uses_channel_level_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            batch_root = Path(tmpdir) / "batch"
            material_dir = batch_root / "loop_01__mat_001"
            workdir = material_dir / "mobility_calculation"
            relaxed_dir = workdir / "01_relax"
            relaxed_dir.mkdir(parents=True, exist_ok=True)
            self._write_structure(material_dir / "POSCAR")
            self._write_structure(relaxed_dir / "CONTCAR")

            (workdir / "material_outcome.json").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "final_status": "completed",
                        "accepted_channels": ["electron_x"],
                        "rejected_channels": ["electron_y"],
                        "stage_status": {
                            "prepare": "success",
                            "relax": "success",
                            "scf": "success",
                            "band": "success",
                            "effective_mass": "success",
                            "strain_loop": "success",
                            "mobility": "success",
                        },
                        "validation_report": {
                            "channel_reviews": {
                                "electron_x": {
                                    "status": "accepted",
                                    "reason": "good fit",
                                    "rel_e1_sigma": 0.10,
                                    "rel_c2d_sigma": 0.05,
                                },
                                "electron_y": {
                                    "status": "rejected",
                                    "reason": "poor fit",
                                    "rel_e1_sigma": 0.10,
                                    "rel_c2d_sigma": 0.05,
                                },
                            }
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            (workdir / "mobility_results.json").write_text(
                json.dumps(
                    {
                        "results_by_direction": {
                            "x": {
                                "n_points": 9,
                                "electron": {
                                    "mobility_cm2_Vs": 1600.0,
                                    "E1_eV": 1.0,
                                    "E1_eV_sigma": 0.08,
                                    "E1_fit_R2": 0.97,
                                    "C2D_J_m2": 52.0,
                                    "C2D_sigma_J_m2": 1.5,
                                    "C2D_fit_R2": 0.98,
                                },
                                "hole": {},
                            },
                            "y": {
                                "n_points": 9,
                                "electron": {
                                    "mobility_cm2_Vs": 900.0,
                                    "E1_eV": 1.0,
                                    "E1_eV_sigma": 0.08,
                                    "E1_fit_R2": 0.81,
                                    "C2D_J_m2": 52.0,
                                    "C2D_sigma_J_m2": 1.5,
                                    "C2D_fit_R2": 0.98,
                                },
                                "hole": {},
                            },
                        }
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            trusted_cif_dir = Path(tmpdir) / "trusted_relaxed_cif"
            result = trusted_channel_rows_for_material(
                material_dir=material_dir,
                round_id="round_00_bootstrap",
                batch_id="bootstrap_batch",
                trusted_cif_dir=trusted_cif_dir,
                thresholds={
                    "min_fit_r2": 0.90,
                    "max_rel_e1_sigma": 0.50,
                    "max_rel_c2d_sigma": 0.20,
                    "min_abs_e1_eV": 0.05,
                },
            )

            self.assertEqual(len(result.trusted_channels), 1)
            self.assertEqual(result.trusted_channels[0]["channel"], "electron_x")
            self.assertEqual(result.material_row["usable_channel_count"], 1)
            self.assertEqual(result.material_row["best_channel"], "electron_x")
            self.assertTrue(Path(result.material_row["relaxed_cif_path"]).exists())
            self.assertFalse(result.rejected_rows)

    def test_build_alignn_round_dataset_combines_base_and_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            base_dir = tmp / "base_cif"
            base_dir.mkdir()
            self._write_structure(base_dir / "base_001.cif")
            (base_dir / "id_prop.csv").write_text("base_001.cif,1.234000\n", encoding="utf-8")

            feedback_dir = tmp / "feedback"
            feedback_dir.mkdir()
            self._write_structure(feedback_dir / "relaxed_001.cif")
            feedback_csv = feedback_dir / "trusted_materials.csv"
            feedback_csv.write_text(
                "round_id,round_index,batch_id,material_id,usable_channel_count,best_channel,best_mobility_cm2_vs,best_target,best_direction,best_carrier,relaxed_cif_path,relaxed_contcar_path,input_poscar_path,structure_hash,source_workdir\n"
                f"loop_01,1,bootstrap_batch,mat_001,1,electron_x,1600.0,3.204120,x,electron,{feedback_dir / 'relaxed_001.cif'},/tmp/CONTCAR,/tmp/POSCAR,hash001,/tmp/workdir\n",
                encoding="utf-8",
            )
            output_dir = tmp / "alignn_dataset"
            manifest_path = tmp / "alignn_manifest.json"

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "build_alignn_round_dataset.py"),
                    "--output-dir",
                    str(output_dir),
                    "--manifest-path",
                    str(manifest_path),
                    "--base-cif-dir",
                    str(base_dir),
                    "--base-labels",
                    str(base_dir / "id_prop.csv"),
                    "--feedback-csv",
                    str(feedback_csv),
                ],
                check=True,
            )

            with (output_dir / "id_prop.csv").open("r", newline="", encoding="utf-8") as handle:
                id_prop_rows = list(csv.reader(handle))
            self.assertEqual(len(id_prop_rows), 2)
            self.assertTrue((output_dir / "base_001.cif").exists())
            self.assertTrue((output_dir / "loop_01__mat_001.cif").exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["counts"]["feedback_samples"], 1)

    def test_build_diffcsp_round_dataset_weights_feedback_and_reaches_min_rows(self) -> None:
        dataset_name = f"test_closed_loop_{uuid.uuid4().hex}"
        dataset_dir = DATA_ROOT / dataset_name
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                base_dir = tmp / "base_cif"
                base_dir.mkdir()
                self._write_structure(base_dir / "base_001.cif")
                self._write_shifted_structure(base_dir / "base_002.cif")

                feedback_dir = tmp / "feedback"
                feedback_dir.mkdir()
                self._write_shifted_structure(feedback_dir / "relaxed_001.cif")
                feedback_csv = feedback_dir / "trusted_materials.csv"
                feedback_csv.write_text(
                    "round_id,round_index,batch_id,material_id,usable_channel_count,best_channel,best_mobility_cm2_vs,best_target,best_direction,best_carrier,relaxed_cif_path,relaxed_contcar_path,input_poscar_path,structure_hash,source_workdir\n"
                    f"loop_01,1,bootstrap_batch,mat_001,1,electron_x,1600.0,3.204120,x,electron,{feedback_dir / 'relaxed_001.cif'},/tmp/CONTCAR,/tmp/POSCAR,hash001,/tmp/workdir\n",
                    encoding="utf-8",
                )
                manifest_path = tmp / "diffcsp_manifest.json"

                subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT_DIR / "build_diffcsp_round_dataset.py"),
                        "--dataset-name",
                        dataset_name,
                        "--manifest-path",
                        str(manifest_path),
                        "--base-cif-dir",
                        str(base_dir),
                        "--feedback-csv",
                        str(feedback_csv),
                        "--feedback-weight",
                        "12",
                        "--min-train-rows",
                        "10000",
                    ],
                    check=True,
                )

                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertEqual(manifest["counts"]["unique_structures"], 3)
                self.assertEqual(manifest["counts"]["feedback_unique_structures"], 1)
                self.assertGreaterEqual(manifest["counts"]["train_rows"], 10000)
                train_rows = read_csv_rows(dataset_dir / "train.csv")
                val_rows = read_csv_rows(dataset_dir / "val.csv")
                test_rows = read_csv_rows(dataset_dir / "test.csv")
                self.assertGreaterEqual(len(train_rows), 10000)
                self.assertEqual(len(val_rows), 3)
                self.assertEqual(len(test_rows), 3)
        finally:
            shutil.rmtree(dataset_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
