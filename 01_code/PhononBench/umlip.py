#!/usr/bin/env python3
"""Compatibility shim for PhononBench's legacy ``umlip`` import.

PhononBench expects a module-level ``umlip`` class exposing:

- ``calculator``: an ASE-compatible calculator
- ``relax_structure(...)``: returns ``[relaxed_atoms, _, _]`` or ``None``

This shim maps that contract onto the official MatterSim calculator and a
simple ASE geometry optimization loop so the vendored PhononBench scripts can
run inside this repository without the original external helper package.
"""

from __future__ import annotations

import os

from ase.optimize import FIRE

try:
    from ase.constraints import FixSymmetry
except ImportError:  # pragma: no cover - optional ASE feature
    FixSymmetry = None

try:
    from ase.filters import FrechetCellFilter as _CellFilter
except ImportError:  # pragma: no cover - older ASE
    try:
        from ase.filters import ExpCellFilter as _CellFilter
    except ImportError:  # pragma: no cover - oldest ASE fallback
        from ase.constraints import UnitCellFilter as _CellFilter

try:
    import torch
except ImportError:  # pragma: no cover - only used to pick a default device
    torch = None

try:
    from mattersim.forcefield import MatterSimCalculator
except ImportError as exc:  # pragma: no cover - runtime environment issue
    raise ImportError(
        "MatterSim is required to use the vendored PhononBench workflow. "
        "Install it with 02_envs/install_phononbench_mattersim.sh first."
    ) from exc


def _default_device() -> str:
    if os.environ.get("MATTERSIM_DEVICE"):
        return os.environ["MATTERSIM_DEVICE"]
    if torch is not None and torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _resolve_load_path(model: str | None) -> str | None:
    token = (model or "").strip().lower()
    if token in {"mattersim-v1", "mattersim-v1-1m", "mattersim-1m", "mattersim"}:
        return None
    if token in {"mattersim-v1-5m", "mattersim-5m"}:
        return "MatterSim-v1.0.0-5M.pth"
    if token.endswith(".pth"):
        return model
    return None


class umlip:
    """Small adapter matching the interface used by PhononBench."""

    def __init__(self, model: str = "mattersim-v1", device: str | None = None):
        load_path = _resolve_load_path(model)
        kwargs = {"device": device or _default_device()}
        if load_path:
            kwargs["load_path"] = load_path
        self.calculator = MatterSimCalculator(**kwargs)
        self.model = model
        self.device = kwargs["device"]

    def relax_structure(
        self,
        atoms,
        fmax: float = 0.005,
        check_cell: bool = False,
        check_connected: bool = False,
        fix_symmetry: bool = True,
        max_steps: int = 500,
    ):
        del check_connected  # Not handled by the MatterSim/ASE compatibility layer.

        relaxed_atoms = atoms.copy()
        if fix_symmetry and FixSymmetry is not None:
            try:
                relaxed_atoms.set_constraint(FixSymmetry(relaxed_atoms))
            except Exception:
                # Symmetry fixing is helpful but optional for robustness.
                pass

        relaxed_atoms.calc = self.calculator
        target = _CellFilter(relaxed_atoms) if check_cell else relaxed_atoms

        try:
            optimizer = FIRE(target, logfile=None)
            optimizer.run(fmax=fmax, steps=max_steps)
        except Exception:
            return None

        return [relaxed_atoms, None, None]
