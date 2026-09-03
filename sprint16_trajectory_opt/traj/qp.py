"""A small OSQP-style ADMM solver for convex quadratic programs.

Solves

    minimize    ½ zᵀP z + qᵀz
    subject to  l ≤ A z ≤ u

with `P` symmetric positive semidefinite. Equality constraints are just rows
with `l = u`; box constraints are rows of the identity.

The whole trajectory optimizer is posed as one QP, so rather than pull in a
solver dependency this implements the ADMM iteration from the OSQP paper: form
one KKT matrix, factor it once, and iterate a linear solve plus a projection
onto the box. It is maybe forty lines of numerics, it converges on the
well-conditioned problems here, and the tests pin it to analytic QP solutions —
which is exactly the point for a portfolio piece: the optimizer is not a black
box.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class QPResult:
    x: np.ndarray
    iterations: int
    primal_residual: float
    dual_residual: float
    converged: bool
    objective: float


def solve_qp(
    P: np.ndarray,
    q: np.ndarray,
    A: np.ndarray,
    l: np.ndarray,
    u: np.ndarray,
    rho: float = 1.0,
    sigma: float = 1e-6,
    alpha: float = 1.6,
    max_iter: int = 12000,
    eps_abs: float = 1e-6,
    eps_rel: float = 1e-6,
) -> QPResult:
    """Solve a convex QP by ADMM (OSQP algorithm) with adaptive ρ.

    Tolerances are scaled by the problem's own magnitudes (the standard OSQP
    absolute+relative criterion), and ρ is adapted from the primal/dual
    residual balance — the two things that make a fixed-parameter ADMM actually
    converge across differently-scaled problems.
    """
    P = np.asarray(P, float)
    q = np.asarray(q, float)
    A = np.asarray(A, float)
    l = np.asarray(l, float)
    u = np.asarray(u, float)
    n = P.shape[0]
    m = A.shape[0]

    def _factor(rho_val: float) -> np.ndarray:
        KKT = np.zeros((n + m, n + m))
        KKT[:n, :n] = P + sigma * np.eye(n)
        KKT[:n, n:] = A.T
        KKT[n:, :n] = A
        KKT[n:, n:] = -(1.0 / rho_val) * np.eye(m)
        return np.linalg.inv(KKT)

    KKT_inv = _factor(rho)
    x = np.zeros(n)
    z = np.zeros(m)
    y = np.zeros(m)

    def _resid():
        Ax = A @ x
        Px = P @ x
        Aty = A.T @ y
        primal = float(np.max(np.abs(Ax - z))) if m else 0.0
        dual = float(np.max(np.abs(Px + q + Aty)))
        eps_pri = eps_abs + eps_rel * (max(float(np.max(np.abs(Ax))) if m else 0.0,
                                            float(np.max(np.abs(z))) if m else 0.0))
        eps_dua = eps_abs + eps_rel * max(float(np.max(np.abs(Px))),
                                          float(np.max(np.abs(Aty))),
                                          float(np.max(np.abs(q))))
        return primal, dual, eps_pri, eps_dua

    converged = False
    it = 0
    for it in range(1, max_iter + 1):
        rhs = np.concatenate([sigma * x - q, z - y / rho])
        sol = KKT_inv @ rhs
        x_tilde = sol[:n]
        nu = sol[n:]
        z_tilde = z + (nu - y) / rho

        z_prev = z
        x = alpha * x_tilde + (1.0 - alpha) * x
        z = np.clip(alpha * z_tilde + (1.0 - alpha) * z_prev + y / rho, l, u)
        y = y + rho * (alpha * z_tilde + (1.0 - alpha) * z_prev - z)

        if it % 25 == 0 or it == 1:
            primal, dual, eps_pri, eps_dua = _resid()
            if primal < eps_pri and dual < eps_dua:
                converged = True
                break
            # OSQP ρ update: rebalance primal/dual residuals.
            if it % 100 == 0 and primal > 0 and dual > 0:
                new_rho = float(np.clip(rho * np.sqrt(primal / dual), 1e-6, 1e6))
                if new_rho > 5 * rho or new_rho < rho / 5:
                    rho = new_rho
                    KKT_inv = _factor(rho)

    primal, dual, eps_pri, eps_dua = _resid()
    obj = float(0.5 * x @ P @ x + q @ x)
    return QPResult(x=x, iterations=it, primal_residual=primal,
                    dual_residual=dual,
                    converged=converged or (primal < eps_pri and dual < eps_dua),
                    objective=obj)
