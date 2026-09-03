"""Point-mass (double-integrator) vehicle model and condensed prediction maps.

The vehicle is a 2-D point mass — horizontal ``x`` and vertical ``h`` — with
acceleration as the control. State is ``[x, vx, h, vh]``, control is
``[ax, ah]``. Each axis is a double integrator, exactly discretized over a step
``dt``:

    x_{k+1} = x_k + vx_k·dt + ½ ax_k·dt²
    vx_{k+1} = vx_k + ax_k·dt        (and likewise for h)

For the optimizer we *condense* the dynamics: every future state is written as
an affine function of the stacked control sequence,

    X = Φ·x₀ + Γ·U

so the trajectory problem becomes a QP in ``U`` alone, with state constraints
turning into linear inequalities on ``U``. This is the standard MPC condensing
step; keeping it in its own module makes the prediction maps independently
testable.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

STATE_DIM = 4      # [x, vx, h, vh]
CONTROL_DIM = 2    # [ax, ah]

# State component indices.
IX, IVX, IH, IVH = 0, 1, 2, 3


@dataclass(frozen=True)
class DoubleIntegrator:
    dt: float

    @property
    def A(self) -> np.ndarray:
        dt = self.dt
        a2 = np.array([[1.0, dt], [0.0, 1.0]])
        A = np.zeros((4, 4))
        A[0:2, 0:2] = a2
        A[2:4, 2:4] = a2
        return A

    @property
    def B(self) -> np.ndarray:
        dt = self.dt
        b2 = np.array([[0.5 * dt * dt], [dt]])
        B = np.zeros((4, 2))
        B[0:2, 0:1] = b2
        B[2:4, 1:2] = b2
        return B

    def step(self, s: np.ndarray, u: np.ndarray) -> np.ndarray:
        return self.A @ s + self.B @ u


def prediction_matrices(model: DoubleIntegrator, N: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (Φ, Γ) mapping x₀ and U to the stacked states X = [s₁ … s_N].

    ``Φ`` is ``(4N × 4)`` and ``Γ`` is ``(4N × 2N)``, lower block-triangular.
    """
    A, B = model.A, model.B
    Phi = np.zeros((STATE_DIM * N, STATE_DIM))
    Gamma = np.zeros((STATE_DIM * N, CONTROL_DIM * N))
    Apow = [np.eye(STATE_DIM)]
    for _ in range(N):
        Apow.append(Apow[-1] @ A)
    for k in range(1, N + 1):
        Phi[STATE_DIM * (k - 1):STATE_DIM * k, :] = Apow[k]
        for j in range(k):
            block = Apow[k - 1 - j] @ B
            Gamma[STATE_DIM * (k - 1):STATE_DIM * k,
                  CONTROL_DIM * j:CONTROL_DIM * (j + 1)] = block
    return Phi, Gamma


def states_from_controls(
    x0: np.ndarray, U: np.ndarray, Phi: np.ndarray, Gamma: np.ndarray
) -> np.ndarray:
    """Roll out states as an ``(N × 4)`` array from a flat control vector ``U``."""
    X = Phi @ x0 + Gamma @ U
    return X.reshape(-1, STATE_DIM)


def rollout(model: DoubleIntegrator, x0: np.ndarray, U: np.ndarray) -> np.ndarray:
    """Direct integration rollout (for cross-checking the condensed maps)."""
    N = U.shape[0] // CONTROL_DIM
    s = x0.copy()
    out = []
    for k in range(N):
        s = model.step(s, U[CONTROL_DIM * k:CONTROL_DIM * (k + 1)])
        out.append(s.copy())
    return np.array(out)
