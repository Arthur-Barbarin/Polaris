"""Approach conditions and fault scenarios for the landing campaign.

Each Scenario bundles the pad pose, sensor/camera config, a wind disturbance,
an optional vision-occlusion window, and the initial approach geometry. All
faults are injected into the synthetic simulation; the `label` doubles as the
supervised label for PCA+GMM triage.

Fault families:
    crosswind      steady lateral wind pushing the vehicle during descent
    gust           wind that switches on partway down
    offset_pad     pad not at the surveyed origin (GPS biased, vision corrects)
    gps_bias       biased GPS (tests the GPS->vision handover)
    low_light      low per-frame detection probability (sparse vision)
    vision_dropout camera occluded in a window near the decision height
    late_acquire   pad not seen until the vehicle is low
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple

import numpy as np

from .camera import CameraConfig
from .pad import LandingPad
from .signals import SensorConfig
from .vehicle import Multirotor


@dataclass
class Scenario:
    name: str
    label: str
    pad: LandingPad = field(default_factory=LandingPad)
    sensor: SensorConfig = field(default_factory=SensorConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    # Constant lateral wind acceleration [m/s^2] (ax, ay).
    wind: Tuple[float, float] = (0.0, 0.0)
    # Optional gust: switches wind on at t_on (adds to constant wind).
    gust_t: Optional[float] = None
    gust: Tuple[float, float] = (0.0, 0.0)
    # Camera occlusion window (t0, t1) [s]; camera unavailable inside it.
    vision_block_t: Optional[Tuple[float, float]] = None
    # Camera acquires only below this altitude [m] (None = from the start).
    acquire_below_z: Optional[float] = None
    # Initial approach geometry.
    init_offset: Tuple[float, float] = (6.0, -4.0)
    init_z: float = 40.0
    # Optional airframe override (None -> default Multirotor).
    vehicle: Optional[Multirotor] = None

    def wind_at(self, t: float) -> np.ndarray:
        wx, wy = self.wind
        if self.gust_t is not None and t >= self.gust_t:
            wx += self.gust[0]
            wy += self.gust[1]
        return np.array([wx, wy, 0.0])


def nominal() -> Scenario:
    return Scenario(name="nominal", label="NOMINAL")


def crosswind() -> Scenario:
    return Scenario(name="crosswind", label="CROSSWIND", wind=(1.6, -1.0))


def gust() -> Scenario:
    # Strong lateral gust hitting on short final, faster than the loop rejects.
    return Scenario(name="gust", label="GUST", gust_t=24.0, gust=(3.2, 2.2))


def offset_pad() -> Scenario:
    return Scenario(name="offset_pad", label="OFFSET_PAD",
                    pad=LandingPad(x=1.8, y=-1.3))


def gps_bias() -> Scenario:
    return Scenario(name="gps_bias", label="GPS_BIAS",
                    sensor=SensorConfig(gps_bias_x=2.5, gps_bias_y=-2.0))


def low_light() -> Scenario:
    return Scenario(name="low_light", label="LOW_LIGHT",
                    camera=CameraConfig(p_detect=0.35, pixel_noise_px=3.0))


def vision_dropout() -> Scenario:
    # Pad occluded on short final (below the decision height) -> go-around.
    return Scenario(name="vision_dropout", label="VISION_DROPOUT",
                    vision_block_t=(24.0, 40.0))


def late_acquire() -> Scenario:
    return Scenario(name="late_acquire", label="LATE_ACQUIRE",
                    acquire_below_z=8.0, init_offset=(9.0, -6.0))


def degraded_vehicle() -> Scenario:
    # Tilt-limited, laggy, low-thrust airframe: the reduced horizontal-accel cap
    # (g*tan14deg) and slower actuator lag make lateral correction sluggish, so
    # it lands with visibly worse tracking under wind (degraded but airworthy).
    # Exists to exercise the Multirotor envelope, which simulate() now accepts.
    return Scenario(name="degraded_vehicle", label="DEGRADED_VEHICLE",
                    wind=(1.2, -0.8),
                    vehicle=Multirotor(name="degraded", tilt_max=np.radians(14),
                                       az_up_max=2.0, az_down_max=1.1, tau_a=0.5))


def narrow_fov() -> Scenario:
    # Narrow field of view + a steep entry offset: the pad geometrically leaves
    # the frame on entry, forcing GPS-only guidance until it re-enters the FOV.
    return Scenario(name="narrow_fov", label="NARROW_FOV",
                    camera=CameraConfig(width_px=240),
                    init_offset=(11.0, -8.0))


ALL_SCENARIOS: dict[str, Callable[[], Scenario]] = {
    "nominal": nominal,
    "crosswind": crosswind,
    "gust": gust,
    "offset_pad": offset_pad,
    "gps_bias": gps_bias,
    "low_light": low_light,
    "vision_dropout": vision_dropout,
    "late_acquire": late_acquire,
    "degraded_vehicle": degraded_vehicle,
    "narrow_fov": narrow_fov,
}
