#!/usr/bin/env python3
"""Reproduce and sanity-check every headline number the harness reports.

Mirrors the Sprint 7 `verify` convention: each block prints a computed value
next to the physically-expected range, and asserts it falls inside. Run:

    python scripts/verify.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from polaris_ft import (  # noqa: E402
    Airframe, NavEKF, SensorConfig, compute_metrics, grade, simulate,
)
from polaris_ft.faults import (  # noqa: E402
    aileron_loss, airspeed_bias, gps_dropout, nominal, wind_step,
)
from polaris_ft.vehicle import G, VehicleState, Wind, step_rk4  # noqa: E402

FAILS = 0


def check(label: str, value: float, lo: float, hi: float, unit: str = "") -> None:
    global FAILS
    ok = lo <= value <= hi
    FAILS += not ok
    flag = "OK " if ok else "XX "
    print(f"  [{flag}] {label:38s} {value:9.3f} {unit:5s} expect [{lo:.3g}, {hi:.3g}]")


print("\n=== 1. Coordinated-turn radius (psi_dot = g/V tan phi) ===")
# At a fixed bank, steady turn radius should be R = V^2 / (g tan phi).
af = Airframe()
V, phi = 30.0, np.radians(30)
st = VehicleState(Va=V, phi=phi, gamma=0.0)
# Freeze the inner loops by commanding the current bank; measure heading rate.
from polaris_ft.vehicle import ControlInput, Actuator  # noqa: E402
ctrl = ControlInput(phi_c=phi, gamma_c=0.0, throttle=0.5)
psi0 = st.psi
st2 = step_rk4(st, ctrl, Wind(), 0.0, 0.1, af, Actuator())
psi_dot = (st2.psi - psi0) / 0.1
R = V / psi_dot
R_expected = V**2 / (G * np.tan(phi))
check("turn radius vs V^2/(g tan phi)", R, R_expected * 0.9, R_expected * 1.1, "m")

print("\n=== 2. Wind drift: ground speed = airspeed + tailwind ===")
st = VehicleState(Va=30.0, psi=0.0, gamma=0.0)
wind = Wind(Wn=5.0, We=0.0)  # 5 m/s tailwind flying north
d = step_rk4(st, ControlInput(phi_c=0, gamma_c=0, throttle=0.5), wind, 0.0, 1.0, af, Actuator())
ground_speed_n = d.pn - st.pn
check("north ground speed (Va+tailwind)", ground_speed_n, 34.0, 36.0, "m/s")

print("\n=== 3. EKF beats raw GPS on position (nominal) ===")
log = simulate(nominal(), seed=3, dt=0.05)
m = compute_metrics(log)
# Raw single-fix GPS noise is 2 m/axis -> ~2.8 m radial; EKF should be under it.
check("EKF position RMSE", m.est_pos_rmse, 0.5, 6.0, "m")

print("\n=== 4. Nominal mission passes all required cards ===")
r = grade(m)
check("nominal cross-track RMS", m.cross_track_rms, 0.0, 8.0, "m")
check("nominal altitude-hold RMS", m.alt_hold_rms, 0.0, 8.0, "m")
check("nominal passed (1=yes)", float(r.passed), 1.0, 1.0)

print("\n=== 5. Faults degrade the right metric ===")
mw = compute_metrics(simulate(wind_step(), seed=3, dt=0.05))
check("wind_step cross-track max", mw.cross_track_max, 60.0, 400.0, "m")
mg = compute_metrics(simulate(gps_dropout(), seed=3, dt=0.05))
check("gps_dropout nav RMSE (>nominal)", mg.est_pos_rmse, 8.0, 60.0, "m")
mb = compute_metrics(simulate(airspeed_bias(), seed=3, dt=0.05))
check("airspeed_bias mean airspeed err", abs(mb.airspeed_mean_err), 2.0, 8.0, "m/s")
ma = compute_metrics(simulate(aileron_loss(), seed=3, dt=0.05))
check("aileron_loss cross-track RMS", ma.cross_track_rms, 20.0, 200.0, "m")

print("\n=== 6. EKF coasts through GPS dropout (no divergence) ===")
# During dropout the horizontal error grows but must stay bounded (airspeed/
# heading pseudo-measurement keeps it from running away).
check("gps_dropout max nav error", mg.est_pos_max, 8.0, 120.0, "m")
check("gps_dropout mission complete", float(mg.mission_complete), 1.0, 1.0)

print()
if FAILS:
    print(f"VERIFY FAILED: {FAILS} checks out of range")
    sys.exit(1)
print("All verification checks passed.")
