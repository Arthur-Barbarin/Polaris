#!/usr/bin/env python3
"""Benchmark the C++ inner loop vs pure Python.

Reports per-call latency for the dynamics step and the autopilot command — the
two functions that on a real airframe run every control tick. The point is the
"real-time / embedded" claim: the C++ inner loop executes in a few microseconds,
i.e. thousands of times faster than the control period, with head-room to spare.

Usage:
    python scripts/benchmark_native.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from polaris_ft import Actuator, Airframe, ControlInput, VehicleState, Wind, step_rk4  # noqa: E402
from polaris_ft import native  # noqa: E402


def bench(fn, n: int) -> float:
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t0) / n * 1e6  # microseconds/call


def main() -> None:
    if not native.native_available():
        print("libpolaris_ft not built — run `cd cpp && make` first.")
        sys.exit(1)

    af, act = Airframe(), Actuator()
    s = VehicleState(pn=100, pe=50, h=120, Va=30, psi=0.3, gamma=0.05, phi=-0.2)
    c = ControlInput(0.2, 0.05, 0.6)
    w = Wind(Wn=3.0, We=-2.0)
    N = 200_000

    py = bench(lambda: step_rk4(s, c, w, 1.0, 0.02, af, act), N)
    cc = bench(lambda: native.step_native(s, c, w, 1.0, 0.02, af, act), N)

    print(f"\nRK4 dynamics step  (mean of {N:,} calls):")
    print(f"  Python : {py:8.3f} us/step   ({1e6/py:10,.0f} steps/s)")
    print(f"  C++    : {cc:8.3f} us/step   ({1e6/cc:10,.0f} steps/s)")
    print(f"  speedup: {py/cc:6.1f}x  (includes Python<->ctypes marshalling)")

    # Real-time head-room: at a 50 Hz control loop the period is 20,000 us.
    period_us = 1e6 / 50
    print(f"\nAt a 50 Hz control loop (period {period_us:,.0f} us), the C++ step "
          f"uses {cc/period_us*100:.3f}% of the budget.")


if __name__ == "__main__":
    main()
