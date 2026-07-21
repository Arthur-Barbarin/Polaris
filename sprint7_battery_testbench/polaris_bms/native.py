"""ctypes wrapper around libpolaris_bms, with pure-Python fallback.

If the shared library is not available (e.g. on Streamlit Cloud where the
.so cannot be built for the host architecture), every class falls back to a
pure-Python implementation that is numerically equivalent to the C++ core.
This lets the dashboard and scripts run without any compiled artifacts.

Build the C++ core for the native path:
    cd cpp && make   ->  build/libpolaris_bms.{so|dylib}
"""
from __future__ import annotations

import ctypes
import enum
import math
import os
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Shared library loader (optional)
# ---------------------------------------------------------------------------

def _find_library() -> Optional[Path]:
    ext = {"Darwin": "dylib", "Linux": "so", "Windows": "dll"}.get(platform.system(), "so")
    name = f"libpolaris_bms.{ext}"
    here = Path(__file__).resolve().parent
    for c in [here.parent / "build" / name, here / name, Path.cwd() / "build" / name]:
        if c.is_file():
            return c
    return None


_lib = None
_lib_path = _find_library()
if _lib_path is not None:
    try:
        _lib = ctypes.CDLL(str(_lib_path))
    except OSError:
        _lib = None


def native_available() -> bool:
    return _lib is not None


# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# OCV table (matches C++ cell_model.cpp kOcvTable)
# ---------------------------------------------------------------------------

_OCV_TABLE = [2.750, 3.250, 3.450, 3.560, 3.620, 3.700, 3.770, 3.850, 3.930, 4.040, 4.200]
_R_GAS = 8.314462618


def ocv_of_soc(soc: float) -> float:
    soc = max(0.0, min(1.0, soc))
    x = soc * (len(_OCV_TABLE) - 1)
    i = int(math.floor(x))
    j = min(i + 1, len(_OCV_TABLE) - 1)
    f = x - i
    return _OCV_TABLE[i] * (1.0 - f) + _OCV_TABLE[j] * f


def _docv_dsoc(soc: float) -> float:
    step = 1.0 / (len(_OCV_TABLE) - 1)
    up = ocv_of_soc(min(1.0, soc + step))
    dn = ocv_of_soc(max(0.0, soc - step))
    return (up - dn) / (2.0 * step)


def _arrhenius(k_ref: float, Ea: float, T_k: float, T_ref_k: float = 298.15) -> float:
    return k_ref * math.exp((Ea / _R_GAS) * (1.0 / T_k - 1.0 / T_ref_k))


# ---------------------------------------------------------------------------
# Pure-Python Cell (mirrors ThéveninCell in C++)
# ---------------------------------------------------------------------------

class _PyCellParams:
    q_nom_ah = 3.20
    eta_charge = 0.995
    T_ref_k = 298.15
    Ea_R0 = 20000.0; Ea_R1 = 35000.0; Ea_R2 = 40000.0
    R0_ref = 0.022; R1_ref = 0.015; C1_ref = 1800.0
    R2_ref = 0.030; C2_ref = 18000.0
    k_cyc = 0.0090; k_cal = 0.00015
    k_r_cyc = 0.0020; k_r_cal = 0.00010
    v_max = 4.20; v_min = 2.75


class _PyCell:
    def __init__(self, soc0: float = 1.0, temperature_k: float = 298.15):
        self._p = _PyCellParams()
        self._soc = 0.0
        self._v_rc1 = 0.0
        self._v_rc2 = 0.0
        self._T_k = temperature_k
        self._cycles_eq = 0.0
        self._time_s = 0.0
        self._fault = Fault.NONE
        self._fault_sev = 0.0
        self._q_now_ah = self._p.q_nom_ah
        self._r0_now = self._p.R0_ref
        self.reset(soc0, temperature_k)

    def reset(self, soc: float, temperature_k: float = 298.15) -> None:
        self._soc = max(0.0, min(1.0, soc))
        self._v_rc1 = 0.0
        self._v_rc2 = 0.0
        self._T_k = temperature_k
        self._cycles_eq = 0.0
        self._time_s = 0.0
        self._refresh_aging()

    def set_temperature(self, T_k: float) -> None:
        self._T_k = T_k

    def set_fault(self, fault: Fault, severity: float = 1.0) -> None:
        self._fault = Fault(int(fault))
        self._fault_sev = max(0.0, severity)

    def _refresh_aging(self) -> None:
        p = self._p
        f, s = self._fault, self._fault_sev
        fault_k = fault_r = 1.0
        if f == Fault.LITHIUM_PLATING:
            fault_k = 1.0 + 2.0 * s
        elif f == Fault.SEI_GROWTH:
            fault_k = 1.0 + 1.2 * s; fault_r = 1.0 + 1.5 * s
        elif f == Fault.INTERNAL_SHORT:
            fault_k = 1.0 + 1.5 * s
        elif f == Fault.ELECTROLYTE_DEPLETION:
            fault_k = 1.0 + 1.5 * s; fault_r = 1.0 + 1.0 * s
        days = self._time_s / 86400.0
        cap_loss = (p.k_cyc * fault_k * math.sqrt(max(0.0, self._cycles_eq))
                    + p.k_cal * math.sqrt(max(0.0, days)))
        self._q_now_ah = p.q_nom_ah * max(0.0, 1.0 - cap_loss)
        self._r0_now = p.R0_ref * (1.0 + p.k_r_cyc * fault_r * self._cycles_eq
                                   + p.k_r_cal * days)

    def _r0(self) -> float:
        base = _arrhenius(self._r0_now, self._p.Ea_R0, self._T_k)
        if self._fault == Fault.INTERNAL_SHORT:
            base *= max(0.05, 1.0 - 0.6 * self._fault_sev)
        return base

    def _r1(self) -> float:
        base = _arrhenius(self._p.R1_ref, self._p.Ea_R1, self._T_k)
        if self._fault == Fault.SEI_GROWTH:
            base *= (1.0 + 0.8 * self._fault_sev)
        if self._fault == Fault.LITHIUM_PLATING:
            base *= (1.0 + 0.5 * self._fault_sev)
        return base

    def _r2(self) -> float:
        base = _arrhenius(self._p.R2_ref, self._p.Ea_R2, self._T_k)
        if self._fault == Fault.ELECTROLYTE_DEPLETION:
            base *= (1.0 + 1.5 * self._fault_sev)
        return base

    def terminal_voltage(self, current_a: float = 0.0) -> float:
        return ocv_of_soc(self._soc) - self._v_rc1 - self._v_rc2 - current_a * self._r0()

    def step(self, current_a: float, dt_s: float) -> float:
        p = self._p
        eta = p.eta_charge if current_a < 0.0 else 1.0
        q_as = self._q_now_ah * 3600.0
        self._soc -= eta * current_a * dt_s / q_as
        self._cycles_eq += abs(current_a) * dt_s / (2.0 * q_as)
        self._time_s += dt_s
        R1 = self._r1(); C1 = p.C1_ref
        R2 = self._r2(); C2 = p.C2_ref
        a1 = dt_s / (R1 * C1); a2 = dt_s / (R2 * C2)
        self._v_rc1 = (self._v_rc1 + (dt_s / C1) * current_a) / (1.0 + a1)
        self._v_rc2 = (self._v_rc2 + (dt_s / C2) * current_a) / (1.0 + a2)
        self._soc = max(0.0, min(1.0, self._soc))
        self._refresh_aging()
        v_term = self.terminal_voltage(current_a)
        if self._fault == Fault.LITHIUM_PLATING and current_a < 0.0 and self._T_k < 288.0:
            v_term -= 0.04 * self._fault_sev
        return v_term

    def snapshot(self) -> CellSnapshot:
        return CellSnapshot(
            soc=self._soc, v_rc1=self._v_rc1, v_rc2=self._v_rc2,
            T_k=self._T_k, cycles_eq=self._cycles_eq, time_s=self._time_s,
            q_now_ah=self._q_now_ah, r0_now=self._r0_now,
        )


# ---------------------------------------------------------------------------
# Pure-Python EKF (mirrors EkfSoc in C++)
# ---------------------------------------------------------------------------

class _PyEkf:
    def __init__(self, soc_guess: float = 0.5, covariance_soc: float = 0.05):
        self._p = _PyCellParams()
        self._x = [0.5, 0.0, 0.0]
        self._P = [[0.0]*3 for _ in range(3)]
        self.initialise(soc_guess, covariance_soc)

    def initialise(self, soc_guess: float, covariance_soc: float = 0.05) -> None:
        self._x = [soc_guess, 0.0, 0.0]
        self._P = [[0.0]*3 for _ in range(3)]
        self._P[0][0] = covariance_soc
        self._P[1][1] = 0.01
        self._P[2][2] = 0.01

    def step(self, current_a: float, v_measured: float, T_k: float, dt_s: float) -> float:
        p = self._p
        R0 = _arrhenius(p.R0_ref, p.Ea_R0, T_k)
        R1 = _arrhenius(p.R1_ref, p.Ea_R1, T_k)
        R2 = _arrhenius(p.R2_ref, p.Ea_R2, T_k)
        C1 = p.C1_ref; C2 = p.C2_ref
        q_as = p.q_nom_ah * 3600.0
        eta = p.eta_charge if current_a < 0.0 else 1.0

        soc_pred = self._x[0] - eta * current_a * dt_s / q_as
        a1 = dt_s / (R1 * C1); a2 = dt_s / (R2 * C2)
        v1_pred = (self._x[1] + (dt_s / C1) * current_a) / (1.0 + a1)
        v2_pred = (self._x[2] + (dt_s / C2) * current_a) / (1.0 + a2)

        f11 = 1.0; f22 = 1.0 / (1.0 + a1); f33 = 1.0 / (1.0 + a2)
        P = self._P
        P00 = f11 * P[0][0] * f11 + 1e-7
        P11 = f22 * P[1][1] * f22 + 1e-5
        P22 = f33 * P[2][2] * f33 + 1e-5
        P01 = f11 * P[0][1] * f22
        P02 = f11 * P[0][2] * f33
        P12 = f22 * P[1][2] * f33

        v_pred = ocv_of_soc(soc_pred) - v1_pred - v2_pred - current_a * R0
        y = v_measured - v_pred
        h0 = _docv_dsoc(soc_pred); h1 = -1.0; h2 = -1.0

        S = (h0 * (h0*P00 + h1*P01 + h2*P02)
           + h1 * (h0*P01 + h1*P11 + h2*P12)
           + h2 * (h0*P02 + h1*P12 + h2*P22) + 5e-4)

        K0 = (h0*P00 + h1*P01 + h2*P02) / S
        K1 = (h0*P01 + h1*P11 + h2*P12) / S
        K2 = (h0*P02 + h1*P12 + h2*P22) / S

        x0 = max(0.0, min(1.0, soc_pred + K0 * y))
        x1 = v1_pred + K1 * y
        x2 = v2_pred + K2 * y
        self._x = [x0, x1, x2]

        IKH00 = 1 - K0*h0; IKH01 = -K0*h1; IKH02 = -K0*h2
        IKH10 =   -K1*h0;  IKH11 = 1-K1*h1; IKH12 = -K1*h2
        IKH20 =   -K2*h0;  IKH21 = -K2*h1;  IKH22 = 1-K2*h2

        self._P[0][0] = max(1e-12, IKH00*P00 + IKH01*P01 + IKH02*P02)
        self._P[1][1] = max(1e-12, IKH10*P01 + IKH11*P11 + IKH12*P12)
        self._P[2][2] = max(1e-12, IKH20*P02 + IKH21*P12 + IKH22*P22)
        off01 = IKH00*P01 + IKH01*P11 + IKH02*P12
        off02 = IKH00*P02 + IKH01*P12 + IKH02*P22
        off12 = IKH10*P02 + IKH11*P12 + IKH12*P22
        self._P[0][1] = self._P[1][0] = off01
        self._P[0][2] = self._P[2][0] = off02
        self._P[1][2] = self._P[2][1] = off12
        return self._x[0]

    @property
    def soc(self) -> float:
        return self._x[0]

    @property
    def soc_variance(self) -> float:
        return self._P[0][0]


# ---------------------------------------------------------------------------
# C++ ctypes wrappers (only set up when the library loaded successfully)
# ---------------------------------------------------------------------------

if _lib is not None:
    def _decl(name, argtypes, restype):
        fn = getattr(_lib, name)
        fn.argtypes = argtypes
        fn.restype = restype
        return fn

    _cell_new   = _decl("polaris_cell_new",          [],                                           ctypes.c_void_p)
    _cell_free  = _decl("polaris_cell_free",          [ctypes.c_void_p],                            None)
    _cell_reset = _decl("polaris_cell_reset",         [ctypes.c_void_p, ctypes.c_double, ctypes.c_double], None)
    _cell_step  = _decl("polaris_cell_step",          [ctypes.c_void_p, ctypes.c_double, ctypes.c_double], ctypes.c_double)
    _cell_set_temp  = _decl("polaris_cell_set_temperature", [ctypes.c_void_p, ctypes.c_double],    None)
    _cell_set_fault = _decl("polaris_cell_set_fault", [ctypes.c_void_p, ctypes.c_int, ctypes.c_double], None)
    _cell_state = _decl("polaris_cell_state",         [ctypes.c_void_p, ctypes.POINTER(ctypes.c_double)], None)
    _cell_term_v = _decl("polaris_cell_terminal_voltage", [ctypes.c_void_p, ctypes.c_double],      ctypes.c_double)
    _ocv        = _decl("polaris_ocv_of_soc",         [ctypes.c_double],                            ctypes.c_double)
    _ekf_new    = _decl("polaris_ekf_new",            [],                                           ctypes.c_void_p)
    _ekf_free   = _decl("polaris_ekf_free",           [ctypes.c_void_p],                            None)
    _ekf_init   = _decl("polaris_ekf_init",           [ctypes.c_void_p, ctypes.c_double, ctypes.c_double], None)
    _ekf_step   = _decl("polaris_ekf_step",           [ctypes.c_void_p, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double], ctypes.c_double)
    _ekf_soc    = _decl("polaris_ekf_soc",            [ctypes.c_void_p],                            ctypes.c_double)
    _ekf_var    = _decl("polaris_ekf_soc_variance",   [ctypes.c_void_p],                            ctypes.c_double)

    class _NativeCell:
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

    class _NativeEkf:
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

    # Override the pure-Python OCV with the C++ version when available
    def ocv_of_soc(soc: float) -> float:  # type: ignore[no-redef]
        return float(_ocv(float(soc)))

    Cell = _NativeCell
    Ekf  = _NativeEkf

else:
    # Pure-Python path (Streamlit Cloud, CI, any env without the .so)
    Cell = _PyCell  # type: ignore[misc]
    Ekf  = _PyEkf   # type: ignore[misc]
