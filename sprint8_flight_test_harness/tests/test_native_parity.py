"""Parity tests: C++ inner loop (libpolaris_ft) vs pure-Python.

Skipped automatically if the shared library has not been built. Build with:
    cd cpp && make
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from polaris_ft import (
    Actuator, Airframe, ControlInput, VehicleState, Wind, compute_metrics,
    default_mission, simulate, step_rk4,
)
from polaris_ft.controller import Autopilot, Gains
from polaris_ft.faults import ALL_SCENARIOS, nominal, wind_step

native = pytest.importorskip("polaris_ft.native")
if not native.native_available():
    pytest.skip("libpolaris_ft not built (run: cd cpp && make)",
                allow_module_level=True)


def test_single_step_parity():
    """One RK4 step must match to ~machine epsilon over random states."""
    af, act = Airframe(), Actuator()
    rng = np.random.default_rng(0)
    worst = 0.0
    for _ in range(2000):
        s = VehicleState(
            pn=rng.uniform(-100, 4000), pe=rng.uniform(-100, 3500),
            h=rng.uniform(80, 140), Va=rng.uniform(15, 42),
            psi=rng.uniform(-3.1, 3.1), gamma=rng.uniform(-0.26, 0.26),
            phi=rng.uniform(-0.78, 0.78))
        c = ControlInput(rng.uniform(-1, 1), rng.uniform(-0.4, 0.4), rng.uniform(0, 1))
        w = Wind(Wn=rng.uniform(-10, 10), We=rng.uniform(-10, 10))
        a = step_rk4(s, c, w, 1.23, 0.05, af, act)
        b = native.step_native(s, c, w, 1.23, 0.05, af, act)
        worst = max(worst, *[abs(getattr(a, k) - getattr(b, k))
                             for k in ("pn", "pe", "h", "Va", "psi", "gamma", "phi")])
    assert worst < 1e-9


def test_control_parity():
    """Autopilot command must match to ~machine epsilon."""
    af, g, m = Airframe(), Gains(), default_mission()
    apy = Autopilot(m, af, g, af.Va_cruise)
    an = native.NativeAutopilot(m, af, g, af.Va_cruise)
    rng = np.random.default_rng(1)
    worst = 0.0
    for _ in range(2000):
        apy.leg_idx = an.leg_idx = int(rng.integers(0, m.n_legs))
        apy._int_V = an._int_V = float(rng.uniform(-20, 20))
        args = (rng.uniform(-100, 4200), rng.uniform(-100, 3600),
                rng.uniform(80, 140), rng.uniform(15, 42), rng.uniform(-3, 3), 0.05)
        cp = apy.command(*args)
        cn = an.command(*args)
        worst = max(worst, abs(cp.phi_c - cn.phi_c), abs(cp.gamma_c - cn.gamma_c),
                    abs(cp.throttle - cn.throttle), abs(apy.leg_idx - an.leg_idx))
    assert worst < 1e-12


@pytest.mark.parametrize("name", list(ALL_SCENARIOS))
def test_full_flight_parity(name):
    """Whole closed-loop trajectories track between backends.

    Bit-exact divergence is not expected (numpy vs libm differ by ~1 ULP on
    transcendentals, which compounds through the feedback loop), but the two
    backends must stay within centimetres over a multi-km flight and reach the
    same verdict.
    """
    lp = simulate(ALL_SCENARIOS[name](), seed=3, dt=0.05, backend="python")
    ln = simulate(ALL_SCENARIOS[name](), seed=3, dt=0.05, backend="native")
    n = min(len(lp.t), len(ln.t))
    assert abs(len(lp.t) - len(ln.t)) <= 2          # mission-complete within 2 ticks
    pos = np.hypot(lp.pn[:n] - ln.pn[:n], lp.pe[:n] - ln.pe[:n])
    assert np.max(pos) < 1.0                          # < 1 m over the whole flight


def test_backend_verdicts_agree():
    """Pass/fail verdict is identical across backends for every scenario."""
    for name, fn in ALL_SCENARIOS.items():
        from polaris_ft import grade
        rp = grade(compute_metrics(simulate(fn(), seed=3, dt=0.1, backend="python")))
        rn = grade(compute_metrics(simulate(fn(), seed=3, dt=0.1, backend="native")))
        assert rp.passed == rn.passed, name
