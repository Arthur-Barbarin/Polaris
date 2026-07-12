#!/usr/bin/env python3
"""Reproduce and sanity-check every headline number, with expected ranges.

Run:  python scripts/verify.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from polaris_pl import (  # noqa: E402
    Camera, CameraConfig, LandingPad, cep, compute_metrics, grade, simulate,
)
from polaris_pl.faults import (  # noqa: E402
    ALL_SCENARIOS, gps_bias, gust, nominal, offset_pad, vision_dropout,
)
from polaris_pl.vehicle import VehicleState  # noqa: E402

FAILS = 0


def check(label, value, lo, hi, unit=""):
    global FAILS
    ok = lo <= value <= hi
    FAILS += not ok
    print(f"  [{'OK ' if ok else 'XX '}] {label:44s} {value:9.3f} {unit:5s} "
          f"expect [{lo:.3g}, {hi:.3g}]")


print("\n=== 1. Vision precision improves as the vehicle descends ===")
rng = np.random.default_rng(0)
cam = Camera(CameraConfig(), LandingPad(), rng)
s_hi = cam.sample(0.0, VehicleState(x=0, y=0, z=30)).sigma_world
cam2 = Camera(CameraConfig(), LandingPad(), rng)
s_lo = cam2.sample(0.0, VehicleState(x=0, y=0, z=2)).sigma_world
check("vision sigma at z=30 m", s_hi, 0.05, 0.20, "m")
check("vision sigma at z=2 m", s_lo, 0.05, 0.09, "m")
check("precision improves (hi/lo ratio)", s_hi / s_lo, 1.5, 10.0, "x")

print("\n=== 2. GPS->vision handover corrects a pad offset / GPS bias ===")
mo = compute_metrics(simulate(offset_pad(), seed=1, dt=0.02))
check("offset_pad touchdown error (pad @1.8,-1.3)", mo.touchdown_lateral, 0.0, 0.5, "m")
mb = compute_metrics(simulate(gps_bias(), seed=1, dt=0.02))
check("gps_bias touchdown error (bias 2.5,-2.0)", mb.touchdown_lateral, 0.0, 0.5, "m")
mn = compute_metrics(simulate(nominal(), seed=1, dt=0.02))
check("disagreement ordering: gps_bias > nominal",
      mb.gps_vision_disagree - mn.gps_vision_disagree, 1.0, 6.0, "m")
check("disagreement ordering: offset_pad > nominal",
      mo.gps_vision_disagree - mn.gps_vision_disagree, 0.5, 6.0, "m")

print("\n=== 3. Nominal touchdown dispersion (CEP) ===")
pts = []
for s in range(40):
    log = simulate(nominal(), seed=s, dt=0.02)
    if log.outcome == "LANDED":
        pts.append([log.touchdown_x, log.touchdown_y])
c = cep(np.array(pts))
check("nominal landings out of 40", float(c.n), 38, 40)
check("nominal CEP50", c.cep50, 0.0, 0.20, "m")
check("nominal CEP95", c.cep95, 0.0, 0.40, "m")
check("nominal touchdown sink rate", mn.touchdown_sink, 0.0, 1.0, "m/s")

print("\n=== 4. Safety go-arounds trigger correctly ===")
gd = simulate(vision_dropout(), seed=1, dt=0.02)
check("vision_dropout -> GO_AROUND (1=yes)", float(gd.outcome == "GO_AROUND"), 1, 1)
gg = simulate(gust(), seed=1, dt=0.02)
check("late gust -> GO_AROUND (1=yes)", float(gg.outcome == "GO_AROUND"), 1, 1)
check("go-around climbs clear (end z)", gg.z[-1], 12.0, 45.0, "m")

print("\n=== 5. Outcome distribution across the campaign (4 seeds) ===")
from collections import defaultdict  # noqa: E402
tally = defaultdict(int)
for name, fn in ALL_SCENARIOS.items():
    for s in range(4):
        tally[grade(compute_metrics(simulate(fn(), seed=s, dt=0.05))).outcome] += 1
print("   ", dict(tally))
check("nominal always PASS (of 4)",
      float(sum(grade(compute_metrics(simulate(nominal(), seed=s, dt=0.05))).passed
                for s in range(4))), 4, 4)

print()
if FAILS:
    print(f"VERIFY FAILED: {FAILS} checks out of range")
    sys.exit(1)
print("All verification checks passed.")
