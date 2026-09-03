"""Pose a minimum-energy trajectory as a single convex QP.

The decision variable is the stacked control sequence ``U`` (accelerations).
Using the condensed dynamics ``X = Φ·x₀ + Γ·U`` every state constraint is linear
in ``U``, so the whole thing is a QP:

    minimize    Σ_k dt·(w_x·ax_k² + w_h·ah_k²)          (control energy)
    subject to  s_N = goal                              (arrive at rest at target)
                |ax| ≤ ax_max, |ah| ≤ ah_max            (thrust / comfort)
                |vx| ≤ vx_max, |vh| ≤ vh_max            (envelope)
                h_k ≥ h_floor                           (terrain / safety floor)
                h_k ≥ h_noise  for k in the corridor    (noise-abatement segment)

The noise-abatement corridor is expressed over a *time-step window*, which for
a monotone A→B repositioning corresponds to the along-track segment over the
noise-sensitive area — and, crucially, keeps the constraint linear (clearing a
peaked obstacle would be non-convex; that limitation is stated honestly in
MODEL.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .dynamics import (
    DoubleIntegrator, prediction_matrices, STATE_DIM, CONTROL_DIM,
    IX, IVX, IH, IVH,
)

INF = 1e12


@dataclass
class TrajectoryProblem:
    dt: float = 0.5
    N: int = 120
    x0: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 300.0, 0.0]))
    xg: np.ndarray = field(default_factory=lambda: np.array([900.0, 0.0, 60.0, 0.0]))
    w_x: float = 1.0
    w_h: float = 1.0
    ax_max: float = 3.0
    ah_max: float = 2.5
    vx_max: float = 45.0
    vh_max: float = 18.0
    h_floor: float = 45.0
    # noise-abatement corridor: steps [k0, k1] must stay at/above h_noise
    noise_k0: int = 40
    noise_k1: int = 80
    h_noise: float = 200.0

    @property
    def T(self) -> float:
        return self.N * self.dt


@dataclass
class QPMatrices:
    P: np.ndarray
    q: np.ndarray
    A: np.ndarray
    l: np.ndarray
    u: np.ndarray
    Phi: np.ndarray
    Gamma: np.ndarray


def _row(Gamma: np.ndarray, k: int, comp: int) -> np.ndarray:
    """Row of Γ giving state component ``comp`` at step ``k`` (1-indexed)."""
    return Gamma[STATE_DIM * (k - 1) + comp, :]


def _phi_row(Phi: np.ndarray, x0: np.ndarray, k: int, comp: int) -> float:
    return float(Phi[STATE_DIM * (k - 1) + comp, :] @ x0)


def build_qp(prob: TrajectoryProblem, include_path_constraints: bool = True) -> QPMatrices:
    """Assemble the QP (P, q, A, l, u) for a trajectory problem."""
    model = DoubleIntegrator(prob.dt)
    N = prob.N
    Phi, Gamma = prediction_matrices(model, N)
    nU = CONTROL_DIM * N

    # --- objective: energy on accelerations ---------------------------------
    w = np.tile(np.array([prob.w_x, prob.w_h]), N) * prob.dt
    P = 2.0 * np.diag(w)          # ½ Uᵀ P U = Σ dt (w_x ax² + w_h ah²)
    q = np.zeros(nU)

    rows: list[np.ndarray] = []
    lo: list[float] = []
    hi: list[float] = []

    # --- terminal equality: s_N = goal --------------------------------------
    for comp in (IX, IVX, IH, IVH):
        r = _row(Gamma, N, comp)
        rhs = float(prob.xg[comp]) - _phi_row(Phi, prob.x0, N, comp)
        rows.append(r); lo.append(rhs); hi.append(rhs)

    # --- control box --------------------------------------------------------
    for k in range(N):
        for c, umax in ((0, prob.ax_max), (1, prob.ah_max)):
            e = np.zeros(nU); e[CONTROL_DIM * k + c] = 1.0
            rows.append(e); lo.append(-umax); hi.append(umax)

    if include_path_constraints:
        for k in range(1, N + 1):
            # velocity envelope
            for comp, vmax in ((IVX, prob.vx_max), (IVH, prob.vh_max)):
                base = _phi_row(Phi, prob.x0, k, comp)
                rows.append(_row(Gamma, k, comp))
                lo.append(-vmax - base); hi.append(vmax - base)
            # altitude floor (and corridor)
            base_h = _phi_row(Phi, prob.x0, k, IH)
            floor = prob.h_floor
            if prob.noise_k0 <= k <= prob.noise_k1:
                floor = max(floor, prob.h_noise)
            rows.append(_row(Gamma, k, IH))
            lo.append(floor - base_h); hi.append(INF)

    A = np.vstack(rows)
    l = np.array(lo)
    u = np.array(hi)
    return QPMatrices(P=P, q=q, A=A, l=l, u=u, Phi=Phi, Gamma=Gamma)


def control_energy(prob: TrajectoryProblem, U: np.ndarray) -> float:
    """Σ_k dt (w_x ax_k² + w_h ah_k²) — the objective value for a control seq."""
    U = U.reshape(-1, CONTROL_DIM)
    return float(prob.dt * np.sum(prob.w_x * U[:, 0] ** 2 + prob.w_h * U[:, 1] ** 2))


def _analytic_axis(p0: float, v0: float, pf: float, vf: float, T: float,
                   times: np.ndarray) -> np.ndarray:
    """Continuous min-energy double-integrator position samples for one axis."""
    dv = vf - v0
    dp = pf - p0 - v0 * T
    M = np.array([[T, T * T / 2.0], [T * T / 2.0, T ** 3 / 6.0]])
    a, b = np.linalg.solve(M, np.array([dv, dp]))
    return p0 + v0 * times + a * times ** 2 / 2.0 + b * times ** 3 / 6.0


def analytic_unconstrained(prob: TrajectoryProblem) -> np.ndarray:
    """Analytic continuous-time optimum (x, h) sampled at the discrete steps."""
    times = np.arange(1, prob.N + 1) * prob.dt
    x = _analytic_axis(prob.x0[IX], prob.x0[IVX], prob.xg[IX], prob.xg[IVX], prob.T, times)
    h = _analytic_axis(prob.x0[IH], prob.x0[IVH], prob.xg[IH], prob.xg[IVH], prob.T, times)
    return np.column_stack([x, h])
