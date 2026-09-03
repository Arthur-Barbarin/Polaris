"""Solve a trajectory problem and score it the way a mission planner would.

Everything here is derived from the QP solution: the control energy, the
constraint margins (does it actually clear the floor and the noise corridor,
does it respect the accel/velocity envelope), the saving over the bang-bang
baseline, and the "price" the noise-abatement corridor adds to the optimal
energy. No tuned scores — every number is an energy, a distance, or a margin.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .dynamics import CONTROL_DIM, IX, IVX, IH, IVH
from .problem import (
    TrajectoryProblem, build_qp, control_energy, analytic_unconstrained,
)
from .baselines import bang_bang_control
from .qp import solve_qp


@dataclass
class TrajectorySolution:
    U: np.ndarray
    X: np.ndarray                 # (N, 4) states
    energy: float
    iterations: int
    primal_residual: float
    dual_residual: float
    converged: bool
    min_floor_clearance: float    # min (h - h_floor) over the path
    min_corridor_clearance: float  # min (h - h_noise) over the corridor (inf if none)
    max_accel: float
    max_speed_h: float
    terminal_error: float         # ‖s_N - goal‖

    @property
    def feasible(self) -> bool:
        return (self.min_floor_clearance > -1e-3
                and self.min_corridor_clearance > -1e-3
                and self.terminal_error < 1e-2)


def _states(prob: TrajectoryProblem, qp, U: np.ndarray) -> np.ndarray:
    X = qp.Phi @ prob.x0 + qp.Gamma @ U
    return X.reshape(-1, 4)


def solve_trajectory(
    prob: TrajectoryProblem, include_path_constraints: bool = True
) -> TrajectorySolution:
    qp = build_qp(prob, include_path_constraints=include_path_constraints)
    res = solve_qp(qp.P, qp.q, qp.A, qp.l, qp.u)
    U = res.x
    X = _states(prob, qp, U)

    h = X[:, IH]
    floor_clear = float(np.min(h - prob.h_floor))
    if prob.noise_k1 >= prob.noise_k0:
        seg = h[prob.noise_k0 - 1:prob.noise_k1]     # steps k0..k1 (1-indexed)
        corridor_clear = float(np.min(seg - prob.h_noise)) if seg.size else float("inf")
    else:
        corridor_clear = float("inf")

    Um = U.reshape(-1, CONTROL_DIM)
    max_accel = float(np.max(np.abs(Um)))
    max_speed_h = float(np.max(np.abs(X[:, IVH])))
    terminal_error = float(np.linalg.norm(X[-1] - prob.xg))

    return TrajectorySolution(
        U=U, X=X, energy=control_energy(prob, U),
        iterations=res.iterations, primal_residual=res.primal_residual,
        dual_residual=res.dual_residual, converged=res.converged,
        min_floor_clearance=floor_clear, min_corridor_clearance=corridor_clear,
        max_accel=max_accel, max_speed_h=max_speed_h, terminal_error=terminal_error,
    )


def analytic_rms(prob: TrajectoryProblem) -> float:
    """RMS position gap between the unconstrained QP optimum and the analytic one."""
    sol = solve_trajectory(prob, include_path_constraints=False)
    ref = analytic_unconstrained(prob)
    got = sol.X[:, [IX, IH]]
    return float(np.sqrt(np.mean(np.sum((got - ref) ** 2, axis=1))))


@dataclass
class BenefitResult:
    energy_optimal: float          # min-energy, no path constraints
    energy_bangbang: float
    savings_fraction: float        # (bb - opt) / bb
    energy_with_corridor: float    # min-energy honoring the noise corridor
    price_of_noise: float          # with_corridor - optimal


def benefit(prob: TrajectoryProblem) -> BenefitResult:
    """Savings vs bang-bang, and the energy price of the noise corridor."""
    opt_free = solve_trajectory(prob, include_path_constraints=False)
    bb = control_energy(prob, bang_bang_control(prob))
    with_corridor = solve_trajectory(prob, include_path_constraints=True)
    e_free = opt_free.energy
    return BenefitResult(
        energy_optimal=e_free,
        energy_bangbang=bb,
        savings_fraction=(bb - e_free) / bb if bb > 0 else float("nan"),
        energy_with_corridor=with_corridor.energy,
        price_of_noise=with_corridor.energy - e_free,
    )


def corridor_sweep(prob: TrajectoryProblem, h_values: list[float]) -> list[tuple[float, float]]:
    """Optimal energy as the noise floor rises — should be monotone increasing."""
    out = []
    for hv in h_values:
        p = TrajectoryProblem(**{**prob.__dict__, "h_noise": hv})
        out.append((hv, solve_trajectory(p, include_path_constraints=True).energy))
    return out
