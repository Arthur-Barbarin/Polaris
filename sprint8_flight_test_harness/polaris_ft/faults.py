"""Fault-injection scenarios for the flight-test campaign.

Each Scenario bundles the environmental + sensor + actuator conditions for one
run, plus a `label` used both as the test-card context and as the supervised
label for the PCA+GMM triage. All faults are injected into the SYNTHETIC
simulation — none of this implies real hardware.

Injected fault families:
    wind_step    steady crosswind that switches on mid-flight
    wind_shear   linearly ramping headwind (shear layer)
    gps_dropout  GPS unavailable for a window (estimator must coast)
    airspeed_bias biased pitot reading (sensor fault)
    aileron_loss reduced roll control effectiveness (actuator fault)
    elevator_loss reduced pitch control effectiveness (actuator fault)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple

import numpy as np

from .signals import SensorConfig
from .vehicle import Actuator, Wind


@dataclass
class Scenario:
    name: str
    label: str
    # Environment
    wind: Wind = field(default_factory=Wind)
    # Sensor + actuator faults
    sensor: SensorConfig = field(default_factory=SensorConfig)
    actuator: Actuator = field(default_factory=Actuator)
    # GPS dropout window (t_start, t_end) in seconds; None = no dropout.
    gps_dropout: Optional[Tuple[float, float]] = None
    # Disturbance onset time (for settling-time measurement), seconds.
    disturbance_t: Optional[float] = None


def _step_gust(t_on: float, dn: float, de: float) -> Callable[[float], Tuple[float, float]]:
    def gust(t: float) -> Tuple[float, float]:
        return (dn, de) if t >= t_on else (0.0, 0.0)
    return gust


def _shear_gust(t_on: float, t_full: float, dn: float, de: float) -> Callable[[float], Tuple[float, float]]:
    def gust(t: float) -> Tuple[float, float]:
        if t <= t_on:
            return (0.0, 0.0)
        frac = min(1.0, (t - t_on) / max(t_full - t_on, 1e-6))
        return (dn * frac, de * frac)
    return gust


def nominal() -> Scenario:
    return Scenario(name="nominal", label="NOMINAL",
                    wind=Wind(Wn=2.0, We=-3.0))


def wind_step() -> Scenario:
    # 8 m/s crosswind (easterly) switches on at t=40 s.
    t_on = 40.0
    return Scenario(
        name="wind_step", label="WIND_STEP",
        wind=Wind(Wn=0.0, We=0.0, gust=_step_gust(t_on, 0.0, 8.0)),
        disturbance_t=t_on,
    )


def wind_shear() -> Scenario:
    # Headwind ramps from 0 to 12 m/s between t=30 s and t=70 s.
    return Scenario(
        name="wind_shear", label="WIND_SHEAR",
        wind=Wind(Wn=0.0, We=0.0, gust=_shear_gust(30.0, 70.0, -12.0, 0.0)),
        disturbance_t=30.0,
    )


def gps_dropout() -> Scenario:
    return Scenario(
        name="gps_dropout", label="GPS_DROPOUT",
        wind=Wind(Wn=2.0, We=-3.0),
        gps_dropout=(45.0, 75.0),
        disturbance_t=45.0,
    )


def airspeed_bias() -> Scenario:
    cfg = SensorConfig(airspeed_bias=-4.0)  # pitot reads 4 m/s slow
    return Scenario(
        name="airspeed_bias", label="AIRSPEED_BIAS",
        wind=Wind(Wn=2.0, We=-3.0),
        sensor=cfg,
        disturbance_t=0.0,
    )


def aileron_loss() -> Scenario:
    return Scenario(
        name="aileron_loss", label="AILERON_LOSS",
        wind=Wind(Wn=2.0, We=-3.0),
        actuator=Actuator(roll_eff=0.45),
        disturbance_t=0.0,
    )


def elevator_loss() -> Scenario:
    return Scenario(
        name="elevator_loss", label="ELEVATOR_LOSS",
        wind=Wind(Wn=2.0, We=-3.0),
        actuator=Actuator(pitch_eff=0.30),
        disturbance_t=0.0,
    )


ALL_SCENARIOS: dict[str, Callable[[], Scenario]] = {
    "nominal": nominal,
    "wind_step": wind_step,
    "wind_shear": wind_shear,
    "gps_dropout": gps_dropout,
    "airspeed_bias": airspeed_bias,
    "aileron_loss": aileron_loss,
    "elevator_loss": elevator_loss,
}
