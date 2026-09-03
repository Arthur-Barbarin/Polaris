import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from traj.dynamics import (
    DoubleIntegrator, prediction_matrices, states_from_controls, rollout,
    CONTROL_DIM,
)


def test_single_step_kinematics():
    m = DoubleIntegrator(dt=2.0)
    s = np.array([0.0, 3.0, 100.0, -1.0])   # x, vx, h, vh
    u = np.array([1.0, 0.5])                # ax, ah
    s1 = m.step(s, u)
    # x = 0 + 3*2 + 0.5*1*4 = 8 ; vx = 3 + 1*2 = 5
    assert np.isclose(s1[0], 8.0) and np.isclose(s1[1], 5.0)
    # h = 100 - 1*2 + 0.5*0.5*4 = 99 ; vh = -1 + 0.5*2 = 0
    assert np.isclose(s1[2], 99.0) and np.isclose(s1[3], 0.0)


def test_condensed_matches_rollout():
    m = DoubleIntegrator(dt=0.7)
    N = 15
    Phi, Gamma = prediction_matrices(m, N)
    x0 = np.array([1.0, 0.0, 250.0, 2.0])
    U = np.random.default_rng(0).normal(size=CONTROL_DIM * N)
    X_condensed = states_from_controls(x0, U, Phi, Gamma)
    X_rollout = rollout(m, x0, U)
    assert np.max(np.abs(X_condensed - X_rollout)) < 1e-10


def test_zero_control_is_ballistic():
    m = DoubleIntegrator(dt=1.0)
    N = 5
    Phi, Gamma = prediction_matrices(m, N)
    x0 = np.array([0.0, 10.0, 100.0, 0.0])
    X = states_from_controls(x0, np.zeros(CONTROL_DIM * N), Phi, Gamma)
    assert np.isclose(X[-1, 0], 50.0)   # constant 10 m/s for 5 s
    assert np.isclose(X[-1, 2], 100.0)  # no vertical motion
