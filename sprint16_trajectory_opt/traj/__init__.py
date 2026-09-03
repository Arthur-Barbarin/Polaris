"""Trajectory Optimization Studio — minimum-energy point-mass trajectories as a QP.

A convex quadratic program, solved by a hand-rolled ADMM solver, generates the
least-control-energy trajectory for a point-mass vehicle subject to a goal, an
acceleration/velocity envelope, an altitude floor, and a noise-abatement
corridor. Every number is an energy, a distance, or a constraint margin.
"""
from __future__ import annotations

from .qp import solve_qp, QPResult
from .dynamics import (
    DoubleIntegrator, prediction_matrices, states_from_controls, rollout,
    STATE_DIM, CONTROL_DIM, IX, IVX, IH, IVH,
)
from .problem import (
    TrajectoryProblem, QPMatrices, build_qp, control_energy,
    analytic_unconstrained,
)
from .baselines import bang_bang_control, bang_bang_axis
from .metrics import (
    TrajectorySolution, solve_trajectory, analytic_rms, benefit, BenefitResult,
    corridor_sweep,
)

__all__ = [
    "solve_qp", "QPResult",
    "DoubleIntegrator", "prediction_matrices", "states_from_controls", "rollout",
    "STATE_DIM", "CONTROL_DIM", "IX", "IVX", "IH", "IVH",
    "TrajectoryProblem", "QPMatrices", "build_qp", "control_energy",
    "analytic_unconstrained",
    "bang_bang_control", "bang_bang_axis",
    "TrajectorySolution", "solve_trajectory", "analytic_rms", "benefit",
    "BenefitResult", "corridor_sweep",
]
