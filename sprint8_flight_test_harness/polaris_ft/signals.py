"""Synthetic sensor / telemetry models.

Turns the true vehicle state into noisy, biased, occasionally-dropped
measurements so the EKF and the test cards are exercised under realistic
flight-log conditions. This is the fixed-wing analogue of the battery
testbench's signals.py (Sprint 7).

IMPORTANT: every measurement here is SYNTHETIC — generated from the simulator,
not captured from real flight hardware. The telemetry logs the harness emits
are simulation output, clearly labelled as such.

Default noise levels are representative of a small-UAV sensor suite:
    GPS position      sigma ~2.0 m (consumer L1 GNSS)
    GPS velocity      sigma ~0.3 m/s
    airspeed (pitot)  sigma ~0.5 m/s
    barometric alt    sigma ~1.5 m, slow bias drift
    heading (mag/gyro)sigma ~2 deg
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class SensorConfig:
    gps_pos_std: float = 2.0        # [m]
    gps_vel_std: float = 0.3        # [m/s]
    airspeed_std: float = 0.5       # [m/s]
    airspeed_bias: float = 0.0      # [m/s]  (fault knob)
    baro_std: float = 1.5           # [m]
    baro_bias: float = 0.0          # [m]
    heading_std: float = np.radians(2.0)  # [rad]
    gps_rate_hz: float = 5.0        # GPS update rate (rest of loop runs faster)


@dataclass
class Measurement:
    t: float
    gps_valid: bool
    gps_n: float
    gps_e: float
    gps_vn: float
    gps_ve: float
    airspeed: float
    baro_h: float
    heading: float


class SensorSuite:
    """Generates measurements from truth, honouring a GPS update rate and
    an externally-controlled GPS-dropout window (set by fault injection)."""

    def __init__(self, cfg: SensorConfig, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        self._last_gps_t = -1e9
        self.gps_available = True  # fault injector may flip this

    def sample(
        self,
        t: float,
        pn: float,
        pe: float,
        h: float,
        vg_n: float,
        vg_e: float,
        Va: float,
        psi: float,
    ) -> Measurement:
        c = self.cfg
        gps_period = 1.0 / c.gps_rate_hz
        do_gps = self.gps_available and (t - self._last_gps_t) >= gps_period - 1e-9
        if do_gps:
            self._last_gps_t = t
            gps_n = pn + self.rng.normal(0, c.gps_pos_std)
            gps_e = pe + self.rng.normal(0, c.gps_pos_std)
            gps_vn = vg_n + self.rng.normal(0, c.gps_vel_std)
            gps_ve = vg_e + self.rng.normal(0, c.gps_vel_std)
        else:
            gps_n = gps_e = gps_vn = gps_ve = np.nan

        airspeed = Va + c.airspeed_bias + self.rng.normal(0, c.airspeed_std)
        baro_h = h + c.baro_bias + self.rng.normal(0, c.baro_std)
        heading = psi + self.rng.normal(0, c.heading_std)

        return Measurement(
            t=t,
            gps_valid=bool(do_gps),
            gps_n=gps_n, gps_e=gps_e, gps_vn=gps_vn, gps_ve=gps_ve,
            airspeed=airspeed, baro_h=baro_h, heading=heading,
        )
