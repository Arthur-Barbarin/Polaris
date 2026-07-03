"""Navigation EKF fusing GPS, barometer, airspeed and heading.

State x = [pn, pe, vn, ve, h]  (horizontal position & ground velocity + altitude).

Prediction uses a constant-velocity kinematic model. Measurement updates:

  * GPS position (pn, pe)        linear, at the GPS rate, DROPS OUT on fault
  * GPS ground velocity (vn, ve) linear, at the GPS rate
  * barometric altitude (h)      linear, every tick
  * airspeed + heading           NONLINEAR velocity pseudo-measurement
                                 (this is the "extended" part): it constrains
                                 ground velocity from Va and psi assuming small
                                 wind, with an inflated covariance so it never
                                 dominates GPS but keeps the horizontal
                                 solution from drifting during GPS dropout.

The controller closes its loop on THIS estimate (position, altitude, and the
course chi = atan2(ve, vn)), so the filter is genuinely in the loop rather than
being a passive post-processor.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .signals import Measurement, SensorConfig


@dataclass
class EkfState:
    x: np.ndarray            # (5,) [pn, pe, vn, ve, h]
    P: np.ndarray            # (5,5) covariance

    @property
    def pn(self) -> float: return float(self.x[0])
    @property
    def pe(self) -> float: return float(self.x[1])
    @property
    def vn(self) -> float: return float(self.x[2])
    @property
    def ve(self) -> float: return float(self.x[3])
    @property
    def h(self) -> float: return float(self.x[4])
    @property
    def course(self) -> float: return float(np.arctan2(self.ve, self.vn))
    @property
    def ground_speed(self) -> float: return float(np.hypot(self.vn, self.ve))


class NavEKF:
    def __init__(
        self,
        cfg: SensorConfig,
        x0: np.ndarray,
        accel_psd: float = 1.5,     # process noise: velocity random-walk [m/s^2 RMS]
        h_psd: float = 0.5,         # altitude process noise [m/s]
        use_airspeed_pseudo: bool = True,
    ):
        self.cfg = cfg
        self.x = np.asarray(x0, dtype=float).copy()
        self.P = np.diag([25.0, 25.0, 4.0, 4.0, 9.0])
        self.accel_psd = accel_psd
        self.h_psd = h_psd
        self.use_airspeed_pseudo = use_airspeed_pseudo

    def predict(self, dt: float) -> None:
        F = np.eye(5)
        F[0, 2] = dt
        F[1, 3] = dt
        self.x = F @ self.x
        # Process noise: white-acceleration model on velocity, random walk on h.
        q = self.accel_psd ** 2
        Qv = q * np.array([
            [dt**3 / 3, dt**2 / 2],
            [dt**2 / 2, dt],
        ])
        Q = np.zeros((5, 5))
        Q[0, 0] = Qv[0, 0]; Q[0, 2] = Qv[0, 1]; Q[2, 0] = Qv[1, 0]; Q[2, 2] = Qv[1, 1]
        Q[1, 1] = Qv[0, 0]; Q[1, 3] = Qv[0, 1]; Q[3, 1] = Qv[1, 0]; Q[3, 3] = Qv[1, 1]
        Q[4, 4] = (self.h_psd * dt) ** 2
        self.P = F @ self.P @ F.T + Q

    def _update_linear(self, H: np.ndarray, z: np.ndarray, R: np.ndarray) -> None:
        y = z - H @ self.x
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        I = np.eye(5)
        self.P = (I - K @ H) @ self.P

    def update(self, m: Measurement) -> None:
        c = self.cfg
        # --- GPS position + velocity (linear), only when valid ---
        if m.gps_valid:
            Hp = np.zeros((2, 5)); Hp[0, 0] = 1; Hp[1, 1] = 1
            self._update_linear(Hp, np.array([m.gps_n, m.gps_e]),
                                 np.diag([c.gps_pos_std**2, c.gps_pos_std**2]))
            Hv = np.zeros((2, 5)); Hv[0, 2] = 1; Hv[1, 3] = 1
            self._update_linear(Hv, np.array([m.gps_vn, m.gps_ve]),
                                 np.diag([c.gps_vel_std**2, c.gps_vel_std**2]))

        # --- Barometric altitude (linear, every tick) ---
        Hh = np.zeros((1, 5)); Hh[0, 4] = 1
        self._update_linear(Hh, np.array([m.baro_h]), np.array([[c.baro_std**2]]))

        # --- Airspeed + heading velocity pseudo-measurement (nonlinear/EKF) ---
        if self.use_airspeed_pseudo:
            self._update_airspeed_heading(m.airspeed, m.heading)

    def _update_airspeed_heading(self, airspeed: float, heading: float) -> None:
        """EKF update: predicted ground velocity from speed magnitude + course.

        h(x) = [ sqrt(vn^2+ve^2), atan2(ve, vn) ]  ->  measured (airspeed, heading)
        Assumes wind is small relative to airspeed; covariance is inflated
        accordingly so GPS remains the primary velocity source.
        """
        vn, ve = self.x[2], self.x[3]
        speed = np.hypot(vn, ve)
        if speed < 1.0:
            return  # ill-conditioned Jacobian at near-zero speed
        h_pred = np.array([speed, np.arctan2(ve, vn)])
        H = np.zeros((2, 5))
        H[0, 2] = vn / speed
        H[0, 3] = ve / speed
        H[1, 2] = -ve / (speed**2)
        H[1, 3] = vn / (speed**2)
        # Inflated R: airspeed != ground speed under wind; heading != course.
        R = np.diag([(self.cfg.airspeed_std * 4.0) ** 2, (np.radians(8.0)) ** 2])
        z = np.array([airspeed, heading])
        y = z - h_pred
        y[1] = (y[1] + np.pi) % (2 * np.pi) - np.pi  # wrap heading innovation
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(5) - K @ H) @ self.P

    def state(self) -> EkfState:
        return EkfState(x=self.x.copy(), P=self.P.copy())
