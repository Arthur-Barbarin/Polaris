import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from traj import TrajectoryProblem, build_qp, control_energy, bang_bang_control
from traj.problem import analytic_unconstrained


def test_energy_objective_matches_manual():
    p = TrajectoryProblem(N=10, dt=0.5)
    U = np.ones(2 * p.N)
    # energy = dt * sum(w_x*1 + w_h*1) = 0.5 * 10 * (1+1) = 10
    assert np.isclose(control_energy(p, U), 10.0)


def test_qp_dimensions_and_equality_rows():
    p = TrajectoryProblem(N=20)
    qp = build_qp(p, include_path_constraints=True)
    assert qp.P.shape == (2 * p.N, 2 * p.N)
    assert qp.A.shape[1] == 2 * p.N
    # first four rows are the terminal equality (l == u)
    assert np.allclose(qp.l[:4], qp.u[:4])


def test_relaxed_qp_has_fewer_rows_than_constrained():
    p = TrajectoryProblem(N=20)
    free = build_qp(p, include_path_constraints=False)
    full = build_qp(p, include_path_constraints=True)
    assert full.A.shape[0] > free.A.shape[0]


def test_analytic_axis_hits_boundary_conditions():
    p = TrajectoryProblem()
    ref = analytic_unconstrained(p)     # (N, 2) of (x, h)
    assert np.isclose(ref[-1, 0], p.xg[0], atol=1e-6)
    assert np.isclose(ref[-1, 1], p.xg[2], atol=1e-6)


def test_bang_bang_reaches_goal_approximately():
    from traj import DoubleIntegrator, rollout
    p = TrajectoryProblem()
    U = bang_bang_control(p)
    X = rollout(DoubleIntegrator(p.dt), p.x0, U)
    assert abs(X[-1, 0] - p.xg[0]) < 5.0     # lands near the horizontal goal
    assert abs(X[-1, 2] - p.xg[2]) < 5.0
