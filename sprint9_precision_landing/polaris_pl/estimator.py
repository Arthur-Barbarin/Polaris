"""Landing navigation filter: fuse IMU + GPS + rangefinder + vision.

State x = [x, y, z, vx, vy, vz]  (vehicle position & velocity relative to the
pad). A constant-acceleration Kalman filter: the IMU acceleration drives the
prediction, and three linear measurement updates correct it:

  * GPS (x, y)        coarse, always available, carries any pad-survey bias
  * rangefinder (z)   precise altitude
  * vision (x, y)     precise but intermittent; noise SHRINKS with altitude,
                      so on short final it dominates GPS and pulls the estimate
                      onto the true pad — the GPS->vision handover.

All measurement models are linear in the state, so this is a linear Kalman
filter (not an EKF) — labelled honestly.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class KFState:
    x: np.ndarray            # (6,)
    P: np.ndarray            # (6,6)

    @property
    def pos(self) -> np.ndarray:
        return self.x[:3].copy()

    @property
    def vel(self) -> np.ndarray:
        return self.x[3:].copy()

    @property
    def lateral_offset(self) -> float:
        return float(np.hypot(self.x[0], self.x[1]))


class LandingKF:
    def __init__(self, x0: np.ndarray, accel_psd: float = 0.6):
        self.x = np.asarray(x0, dtype=float).copy()
        self.P = np.diag([4.0, 4.0, 1.0, 1.0, 1.0, 1.0])
        self.accel_psd = accel_psd

    def predict(self, accel: np.ndarray, dt: float) -> None:
        F = np.eye(6)
        F[0, 3] = F[1, 4] = F[2, 5] = dt
        B = np.zeros((6, 3))
        B[0, 0] = B[1, 1] = B[2, 2] = 0.5 * dt * dt
        B[3, 0] = B[4, 1] = B[5, 2] = dt
        self.x = F @ self.x + B @ np.asarray(accel, dtype=float)
        # White-acceleration process noise.
        q = self.accel_psd ** 2
        Q = np.zeros((6, 6))
        for i in range(3):
            Q[i, i] = q * dt ** 3 / 3
            Q[i, i + 3] = q * dt ** 2 / 2
            Q[i + 3, i] = q * dt ** 2 / 2
            Q[i + 3, i + 3] = q * dt
        self.P = F @ self.P @ F.T + Q

    def _update(self, H: np.ndarray, z: np.ndarray, R: np.ndarray) -> None:
        y = z - H @ self.x
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(6) - K @ H) @ self.P

    def update_gps(self, gx: float, gy: float, std: float) -> None:
        H = np.zeros((2, 6)); H[0, 0] = 1; H[1, 1] = 1
        self._update(H, np.array([gx, gy]), np.diag([std ** 2, std ** 2]))

    def update_range(self, z_meas: float, std: float) -> None:
        H = np.zeros((1, 6)); H[0, 2] = 1
        self._update(H, np.array([z_meas]), np.array([[std ** 2]]))

    def update_vision(self, vx: float, vy: float, std: float) -> None:
        H = np.zeros((2, 6)); H[0, 0] = 1; H[1, 1] = 1
        self._update(H, np.array([vx, vy]), np.diag([std ** 2, std ** 2]))

    def state(self) -> KFState:
        return KFState(x=self.x.copy(), P=self.P.copy())
