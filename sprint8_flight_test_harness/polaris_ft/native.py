"""ctypes wrapper around libpolaris_ft (the C++ inner loop).

Exposes the same dynamics step and autopilot command as the pure-Python
vehicle.py / controller.py, but executed in C++. Locate the shared library
next to the package or in the dev-time build/ folder. If the library is not
built, `native_available()` returns False and callers fall back to Python.

Build it with:
    cd cpp && make        # -> build/libpolaris_ft.{so|dylib}
"""
from __future__ import annotations

import ctypes
import platform
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from .controller import Gains
from .mission import Mission
from .vehicle import Actuator, Airframe, ControlInput, VehicleState, Wind


def _library_path() -> Optional[Path]:
    ext = {"Darwin": "dylib", "Linux": "so", "Windows": "dll"}.get(platform.system(), "so")
    name = f"libpolaris_ft.{ext}"
    here = Path(__file__).resolve().parent
    for c in [here.parent / "build" / name, here / name, Path.cwd() / "build" / name]:
        if c.is_file():
            return c
    return None


_lib = None
_path = _library_path()
if _path is not None:
    _lib = ctypes.CDLL(str(_path))

    _lib.ft_wrap_pi.argtypes = [ctypes.c_double]
    _lib.ft_wrap_pi.restype = ctypes.c_double

    _dp = ctypes.POINTER(ctypes.c_double)
    _lib.ft_step.argtypes = [_dp, _dp, _dp, ctypes.c_double, _dp, _dp, _dp]
    _lib.ft_step.restype = None
    _lib.ft_control.argtypes = [
        ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
        ctypes.c_double, ctypes.c_double, _dp, ctypes.c_int, ctypes.c_int,
        ctypes.c_double, ctypes.c_double, _dp, _dp, _dp,
    ]
    _lib.ft_control.restype = None


def native_available() -> bool:
    return _lib is not None


def library_path() -> Optional[str]:
    return str(_path) if _path else None


def _af_array(af: Airframe) -> np.ndarray:
    return np.array([af.Va_cruise, af.Va_min, af.Va_max, af.phi_max, af.gamma_max,
                     af.tau_phi, af.tau_gamma, af.thrust_accel_max, af.drag_coef],
                    dtype=np.float64)


def _gains_array(g: Gains) -> np.ndarray:
    return np.array([g.k_path, g.chi_inf, g.k_chi, g.k_h, g.kp_V, g.ki_V], dtype=np.float64)


def _ptr(a: np.ndarray):
    return a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))


def step_native(
    state: VehicleState, ctrl: ControlInput, wind: Wind, t: float, dt: float,
    airframe: Airframe, act: Actuator,
) -> VehicleState:
    """RK4 step in C++. Wind is sampled at t, t+dt/2, t+dt for RK4 parity."""
    s = np.array([state.pn, state.pe, state.h, state.Va, state.psi,
                  state.gamma, state.phi], dtype=np.float64)
    c = np.array([ctrl.phi_c, ctrl.gamma_c, ctrl.throttle], dtype=np.float64)
    wn_t, we_t = wind.sample(t)
    wn_m, we_m = wind.sample(t + dt / 2)
    wn_e, we_e = wind.sample(t + dt)
    w = np.array([wn_t, we_t, wn_m, we_m, wn_e, we_e], dtype=np.float64)
    a = np.array([act.roll_authority, act.pitch_authority, act.thr_eff,
                  act.roll_rate_factor, act.pitch_rate_factor], dtype=np.float64)
    af = _af_array(airframe)
    out = np.zeros(7, dtype=np.float64)
    _lib.ft_step(_ptr(s), _ptr(c), _ptr(w), ctypes.c_double(dt),
                 _ptr(af), _ptr(a), _ptr(out))
    return VehicleState(pn=out[0], pe=out[1], h=out[2], Va=out[3],
                        psi=out[4], gamma=out[5], phi=out[6])


class NativeAutopilot:
    """Drop-in replacement for controller.Autopilot backed by C++ ft_control."""

    def __init__(self, mission: Mission, airframe: Airframe, gains: Gains,
                 Va_cmd: float):
        self.mission = mission
        self.airframe = airframe
        self.gains = gains
        self.Va_cmd = Va_cmd
        self.leg_idx = 0
        self._int_V = 0.0
        self._legs = np.array(
            [[w.n, w.e, w.h] for w in mission.waypoints], dtype=np.float64
        ).reshape(-1)
        self._n_wps = len(mission.waypoints)
        self._af = _af_array(airframe)
        self._g = _gains_array(gains)

    def reset(self) -> None:
        self.leg_idx = 0
        self._int_V = 0.0

    def command(self, pn: float, pe: float, h: float, Va: float, chi: float,
                dt: float) -> ControlInput:
        out = np.zeros(5, dtype=np.float64)
        _lib.ft_control(
            ctypes.c_double(pn), ctypes.c_double(pe), ctypes.c_double(h),
            ctypes.c_double(Va), ctypes.c_double(chi), ctypes.c_double(dt),
            _ptr(self._legs), ctypes.c_int(self._n_wps),
            ctypes.c_int(self.leg_idx), ctypes.c_double(self._int_V),
            ctypes.c_double(self.Va_cmd), _ptr(self._g), _ptr(self._af),
            _ptr(out),
        )
        self.leg_idx = int(out[3])
        self._int_V = float(out[4])
        return ControlInput(phi_c=out[0], gamma_c=out[1], throttle=out[2])
