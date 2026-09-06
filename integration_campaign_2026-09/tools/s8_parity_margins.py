"""S8: report the ACTUAL measured native-vs-Python deviations, not just pass/fail.

tests/test_native_parity.py asserts bounds (1e-9, 1e-12, 1 m). This prints the
numbers those assertions were compared against, so the campaign report can cite
measured margins instead of 'the test passed'.
"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sprint8_flight_test_harness"))

from polaris_ft import (Actuator, Airframe, ControlInput, VehicleState, Wind,
                        compute_metrics, default_mission, grade, simulate, step_rk4)
from polaris_ft.controller import Autopilot, Gains
from polaris_ft.faults import ALL_SCENARIOS
from polaris_ft import native

print("native_available:", native.native_available())
assert native.native_available(), "native path not loaded - probe is meaningless"

af, act = Airframe(), Actuator()
rng = np.random.default_rng(0)
worst = 0.0
for _ in range(2000):
    s = VehicleState(pn=rng.uniform(-100, 4000), pe=rng.uniform(-100, 3500),
                     h=rng.uniform(80, 140), Va=rng.uniform(15, 42),
                     psi=rng.uniform(-3.1, 3.1), gamma=rng.uniform(-0.26, 0.26),
                     phi=rng.uniform(-0.78, 0.78))
    c = ControlInput(rng.uniform(-1, 1), rng.uniform(-0.4, 0.4), rng.uniform(0, 1))
    w = Wind(Wn=rng.uniform(-10, 10), We=rng.uniform(-10, 10))
    a = step_rk4(s, c, w, 1.23, 0.05, af, act)
    b = native.step_native(s, c, w, 1.23, 0.05, af, act)
    worst = max(worst, *[abs(getattr(a, k) - getattr(b, k))
                         for k in ("pn", "pe", "h", "Va", "psi", "gamma", "phi")])
print(f"single RK4 step   worst abs deviation = {worst:.6e}   (assert < 1e-9)")

g, m = Gains(), default_mission()
apy, an = Autopilot(m, af, g, af.Va_cruise), native.NativeAutopilot(m, af, g, af.Va_cruise)
rng = np.random.default_rng(1)
worst = 0.0
for _ in range(2000):
    apy.leg_idx = an.leg_idx = int(rng.integers(0, m.n_legs))
    apy._int_V = an._int_V = float(rng.uniform(-20, 20))
    args = (rng.uniform(-100, 4200), rng.uniform(-100, 3600),
            rng.uniform(80, 140), rng.uniform(15, 42), rng.uniform(-3, 3), 0.05)
    cp, cn = apy.command(*args), an.command(*args)
    worst = max(worst, abs(cp.phi_c - cn.phi_c), abs(cp.gamma_c - cn.gamma_c),
                abs(cp.throttle - cn.throttle), abs(apy.leg_idx - an.leg_idx))
print(f"autopilot command worst abs deviation = {worst:.6e}   (assert < 1e-12)")

print("\nfull closed-loop flights, dt=0.05, seed=3   (assert max pos < 1.0 m, len delta <= 2)")
print(f"  {'scenario':28s} {'max |pos| (m)':>14s} {'len delta':>10s}  verdict py/native")
for name, fn in ALL_SCENARIOS.items():
    lp = simulate(fn(), seed=3, dt=0.05, backend="python")
    ln = simulate(fn(), seed=3, dt=0.05, backend="native")
    k = min(len(lp.t), len(ln.t))
    pos = float(np.max(np.hypot(lp.pn[:k] - ln.pn[:k], lp.pe[:k] - ln.pe[:k])))
    rp = grade(compute_metrics(simulate(fn(), seed=3, dt=0.1, backend="python")))
    rn = grade(compute_metrics(simulate(fn(), seed=3, dt=0.1, backend="native")))
    print(f"  {name:28s} {pos:14.6e} {len(lp.t)-len(ln.t):10d}  "
          f"{'PASS' if rp.passed else 'FAIL'}/{'PASS' if rn.passed else 'FAIL'}"
          f"{'' if rp.passed == rn.passed else '   <-- MISMATCH'}")
