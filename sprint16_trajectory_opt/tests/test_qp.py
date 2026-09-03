import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from traj.qp import solve_qp


def test_box_constraint_projection():
    # min ½x² s.t. x >= 1  -> x = 1
    r = solve_qp(np.eye(1), np.zeros(1), np.eye(1), np.array([1.0]), np.array([np.inf]))
    assert abs(r.x[0] - 1.0) < 1e-5 and r.converged


def test_equality_constrained_simplex_center():
    # min ½‖x‖² s.t. sum x = 1 -> 1/3 each
    n = 3
    r = solve_qp(np.eye(n), np.zeros(n), np.ones((1, n)), np.array([1.0]), np.array([1.0]))
    assert np.allclose(r.x, 1.0 / 3, atol=1e-5)


def test_box_saturation_both_sides():
    for a, exp in ((5.0, 2.0), (-3.0, 0.0), (1.2, 1.2)):
        r = solve_qp(np.eye(1), np.array([-a]), np.eye(1), np.array([0.0]), np.array([2.0]))
        assert abs(r.x[0] - exp) < 1e-5


def test_matches_closed_form_equality_qp():
    rng = np.random.default_rng(0)
    n = 6
    M = rng.normal(size=(n, n))
    P = M @ M.T + 0.1 * np.eye(n)
    q = rng.normal(size=n)
    A = rng.normal(size=(2, n))
    b = rng.normal(size=2)
    K = np.block([[P, A.T], [A, np.zeros((2, 2))]])
    x_star = np.linalg.solve(K, np.concatenate([-q, b]))[:n]
    r = solve_qp(P, q, A, b, b)     # l = u = b  -> equality
    assert np.max(np.abs(r.x - x_star)) < 1e-6
    assert r.converged


def test_reports_objective_and_residuals():
    r = solve_qp(np.eye(2), np.array([-1.0, -2.0]), np.eye(2),
                 np.array([-5.0, -5.0]), np.array([5.0, 5.0]))
    assert np.allclose(r.x, [1.0, 2.0], atol=1e-5)   # unconstrained minimum
    assert r.primal_residual < 1e-5 and r.dual_residual < 1e-5
