"""Non-vision sensors: coarse GPS, a downward rangefinder, and an IMU.

GPS is referenced to the *expected* pad location (the surveyed origin). If the
pad has actually moved (`offset_pad` fault), GPS therefore carries a standing
bias equal to the pad offset — which only vision can correct. That handover
(coarse GPS far out, precise vision on short final) is the whole story.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .vehicle import VehicleState


@dataclass
class SensorConfig:
    gps_xy_std: float = 1.2          # horizontal GPS noise [m]
    gps_bias_x: float = 0.0          # standing GPS bias [m] (fault knob)
    gps_bias_y: float = 0.0
    gps_rate_hz: float = 5.0
    range_std: float = 0.05          # rangefinder altitude noise [m]
    accel_std: float = 0.15          # IMU acceleration noise [m/s^2]


@dataclass
class GpsMeasurement:
    valid: bool
    x: float
    y: float


class SensorSuite:
    def __init__(self, cfg: SensorConfig, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        self._last_gps_t = -1e9

    def gps(self, t: float, state: VehicleState) -> GpsMeasurement | None:
        c = self.cfg
        if (t - self._last_gps_t) < 1.0 / c.gps_rate_hz - 1e-9:
            return None
        self._last_gps_t = t
        return GpsMeasurement(
            valid=True,
            x=state.x + c.gps_bias_x + self.rng.normal(0.0, c.gps_xy_std),
            y=state.y + c.gps_bias_y + self.rng.normal(0.0, c.gps_xy_std),
        )

    def rangefinder(self, state: VehicleState) -> float:
        return state.z + self.rng.normal(0.0, self.cfg.range_std)

    def imu_accel(self, state: VehicleState) -> np.ndarray:
        s = self.cfg.accel_std
        return np.array([state.ax + self.rng.normal(0, s),
                         state.ay + self.rng.normal(0, s),
                         state.az + self.rng.normal(0, s)])
