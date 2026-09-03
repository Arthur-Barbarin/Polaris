"""Naive reference trajectories to measure the optimizer against.

The classic foil for a *minimum-energy* trajectory is a *minimum-time*
bang-bang profile: accelerate hard, then brake hard. It reaches the goal but
spends the most control effort doing so. For a rest-to-rest double integrator
the energy gap is exact — bang-bang costs ``16 D²/T³`` per axis versus the
minimum-energy ``12 D²/T³`` — a 25% penalty the optimizer should recover.
"""
from __future__ import annotations

import numpy as np

from .dynamics import CONTROL_DIM, IX, IH
from .problem import TrajectoryProblem


def bang_bang_axis(p0: float, pf: float, T: float, dt: float, N: int) -> np.ndarray:
    """Rest-to-rest constant-acceleration (triangular-velocity) accelerations."""
    D = pf - p0
    amag = 4.0 * D / (T * T)          # +amag first half, -amag second half
    a = np.zeros(N)
    half = N // 2
    a[:half] = amag
    a[half:] = -amag
    return a


def bang_bang_control(prob: TrajectoryProblem) -> np.ndarray:
    """Bang-bang control sequence for both axes, flattened to ``U``."""
    ax = bang_bang_axis(prob.x0[IX], prob.xg[IX], prob.T, prob.dt, prob.N)
    ah = bang_bang_axis(prob.x0[IH], prob.xg[IH], prob.T, prob.dt, prob.N)
    U = np.empty(CONTROL_DIM * prob.N)
    U[0::2] = ax
    U[1::2] = ah
    return U
