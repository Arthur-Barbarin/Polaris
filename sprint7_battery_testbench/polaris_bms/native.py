"""ctypes wrapper around libpolaris_bms.

Locates the shared library next to the package, falling back to the build/
folder used during development.
"""
from __future__ import annotations

import ctypes
import enum
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _library_path() -> Path:
    ext = {"Darwin": "dylib", "Linux": "so", "Windows": "dll"}.get(platform.system(), "so")
    name = f"libpolaris_bms.{ext}"
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / "build" / name,
        here / name,
        Path.cwd() / "build" / name,
    ]
    for c in candidates:
        if c.is_file():
            return c
    searched = "\n  ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        f"Could not find {name}. Build the C++ core first:\n"
        f"  cd cpp && make\nSearched:\n  {searched}"
    )


_lib = ctypes.CDLL(str(_library_path()))


def _decl(name: str, argtypes, restype):
    fn = getattr(_lib, name)
    fn.argtypes = argtypes
    fn.restype = restype
    return fn


# Cell
_cell_new = _decl("polaris_cell_new", [], ctypes.c_void_p)
_cell_free = _decl("polaris_cell_free", [ctypes.c_void_p], None)
_cell_reset = _decl("polaris_cell_reset", [ctypes.c_void_p, ctypes.c_double, ctypes.c_double], None)
_cell_step = _decl("polaris_cell_step", [ctypes.c_void_p, ctypes.c_double, ctypes.c_double], ctypes.c_double)
_cell_set_temp = _decl("polaris_cell_set_temperature", [ctypes.c_void_p, ctypes.c_double], None)
_cell_set_fault = _decl("polaris_cell_set_fault", [ctypes.c_void_p, ctypes.c_int, ctypes.c_double], None)
_cell_state = _decl("polaris_cell_state", [ctypes.c_void_p, ctypes.POINTER(ctypes.c_double)], None)
_cell_term_v = _decl("polaris_cell_terminal_voltage", [ctypes.c_void_p, ctypes.c_double], ctypes.c_double)
_ocv = _decl("polaris_ocv_of_soc", [ctypes.c_double], ctypes.c_double)

# EKF
_ekf_new = _decl("polaris_ekf_new", [], ctypes.c_void_p)
_ekf_free = _decl("polaris_ekf_free", [ctypes.c_void_p], None)
_ekf_init = _decl("polaris_ekf_init", [ctypes.c_void_p, ctypes.c_double, ctypes.c_double], None)
_ekf_step = _decl(
    "polaris_ekf_step",
    [ctypes.c_void_p, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double],
    ctypes.c_double,
)
_ekf_soc = _decl("polaris_ekf_soc", [ctypes.c_void_p], ctypes.c_double)
_ekf_var = _decl("polaris_ekf_soc_variance", [ctypes.c_void_p], ctypes.c_double)


class Fault(enum.IntEnum):
    NONE = 0
    INTERNAL_SHORT = 1
    LITHIUM_PLATING = 2
    SEI_GROWTH = 3
    ELECTROLYTE_DEPLETION = 4


@dataclass
class CellSnapshot:
    soc: float
    v_rc1: float
    v_rc2: float
    T_k: float
    cycles_eq: float
    time_s: float
    q_now_ah: float
    r0_now: float


class Cell:
    """High-level wrapper around the C++ 2nd-order Thévenin cell."""

    def __init__(self, soc0: float = 1.0, temperature_k: float = 298.15):
        self._h = _cell_new()
        if not self._h:
            raise MemoryError("polaris_cell_new returned NULL")
        _cell_reset(self._h, float(soc0), float(temperature_k))

    def __del__(self):
        try:
            _cell_free(self._h)
        except Exception:
            pass

    def reset(self, soc: float, temperature_k: float = 298.15) -> None:
        _cell_reset(self._h, float(soc), float(temperature_k))

    def step(self, current_a: float, dt_s: float) -> float:
        """Apply current for dt seconds; returns terminal voltage."""
        return float(_cell_step(self._h, float(current_a), float(dt_s)))

    def set_temperature(self, T_k: float) -> None:
        _cell_set_temp(self._h, float(T_k))

    def set_fault(self, fault: Fault, severity: float = 1.0) -> None:
        _cell_set_fault(self._h, int(fault), float(severity))

    def terminal_voltage(self, current_a: float = 0.0) -> float:
        return float(_cell_term_v(self._h, float(current_a)))

    def snapshot(self) -> CellSnapshot:
        buf = (ctypes.c_double * 8)()
        _cell_state(self._h, buf)
        return CellSnapshot(*buf)


class Ekf:
    """Extended Kalman Filter SOC estimator (C++ backed)."""

    def __init__(self, soc_guess: float = 0.5, covariance_soc: float = 0.05):
        self._h = _ekf_new()
        if not self._h:
            raise MemoryError("polaris_ekf_new returned NULL")
        _ekf_init(self._h, float(soc_guess), float(covariance_soc))

    def __del__(self):
        try:
            _ekf_free(self._h)
        except Exception:
            pass

    def initialise(self, soc_guess: float, covariance_soc: float = 0.05) -> None:
        _ekf_init(self._h, float(soc_guess), float(covariance_soc))

    def step(self, current_a: float, v_measured: float, T_k: float, dt_s: float) -> float:
        return float(_ekf_step(self._h, float(current_a), float(v_measured), float(T_k), float(dt_s)))

    @property
    def soc(self) -> float:
        return float(_ekf_soc(self._h))

    @property
    def soc_variance(self) -> float:
        return float(_ekf_var(self._h))


def ocv_of_soc(soc: float) -> float:
    """Open-circuit voltage at the given state of charge (0..1)."""
    return float(_ocv(float(soc)))
