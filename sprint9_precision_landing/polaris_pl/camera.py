"""Downward-facing camera + fiducial detection model (synthetic measurements).

The camera is a nadir-pointing pinhole. Given the vehicle's true horizontal
offset from the pad and its height z, the pad projects to image coordinates

    u = f * (pad_x - x) / z ,   v = f * (pad_y - y) / z      [pixels]

The pad is *detectable* only when it lies inside the field of view
(|u|, |v| <= W/2) AND a per-frame detection succeeds (misses model motion blur /
low contrast). When detected, the returned relative-position measurement has
image-plane (pixel) noise back-projected to metres:

    sigma_world = z * pixel_noise / f

so vision precision IMPROVES as the vehicle descends (closer pad = bigger,
sharper marker) — the key reason a GPS→vision handover buys you a centimetre-
class touchdown. This is a synthetic *measurement* model (projected fiducial
geometry), not real image pixels; no images are rendered or processed.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .pad import LandingPad
from .vehicle import VehicleState


@dataclass
class CameraConfig:
    focal_px: float = 800.0          # focal length [px]
    width_px: int = 1280             # sensor width [px] (square FOV assumed)
    pixel_noise_px: float = 1.5      # detection centroid noise [px, 1-sigma]
    sigma_floor_m: float = 0.05      # irreducible measurement floor [m]
    p_detect: float = 0.97           # per-frame detection prob when in FOV
    rate_hz: float = 20.0            # camera frame rate

    @property
    def half_fov_tan(self) -> float:
        """tan(HFOV/2) = (W/2) / f — the in-FOV gate on offset/height."""
        return (self.width_px / 2.0) / self.focal_px


@dataclass
class VisionMeasurement:
    t: float
    valid: bool               # pad detected this frame
    in_fov: bool              # pad geometrically inside the frame
    rel_x: float              # measured vehicle-x relative to pad [m]
    rel_y: float              # measured vehicle-y relative to pad [m]
    u: float                  # image coord [px] (for viz; nan if not in FOV)
    v: float
    sigma_world: float        # 1-sigma measurement noise at this height [m]


class Camera:
    def __init__(self, cfg: CameraConfig, pad: LandingPad, rng: np.random.Generator):
        self.cfg = cfg
        self.pad = pad
        self.rng = rng
        self._last_t = -1e9
        self.available = True     # fault injector may force this False (occlusion)

    def sample(self, t: float, state: VehicleState) -> VisionMeasurement | None:
        """Return a measurement at the camera rate, or None between frames."""
        c = self.cfg
        if (t - self._last_t) < 1.0 / c.rate_hz - 1e-9:
            return None
        self._last_t = t

        z = max(state.z, 0.05)
        # Pad offset in the image (pad relative to vehicle), projected.
        off_x = self.pad.x - state.x
        off_y = self.pad.y - state.y
        u = c.focal_px * off_x / z
        v = c.focal_px * off_y / z
        in_fov = (abs(off_x / z) <= c.half_fov_tan and
                  abs(off_y / z) <= c.half_fov_tan)

        detected = self.available and in_fov and (self.rng.random() < c.p_detect)
        # Projected pixel noise shrinks with altitude, but never below an
        # irreducible floor (marker resolution, centroid quantisation, camera-
        # IMU timing/alignment) — so touchdown accuracy is bounded, not zero.
        sigma_world = float(np.hypot(z * c.pixel_noise_px / c.focal_px, c.sigma_floor_m))
        if not detected:
            return VisionMeasurement(t=t, valid=False, in_fov=in_fov,
                                     rel_x=np.nan, rel_y=np.nan,
                                     u=(u if in_fov else np.nan),
                                     v=(v if in_fov else np.nan),
                                     sigma_world=sigma_world)

        # Vehicle position relative to the pad, with back-projected pixel noise.
        rel_x = (state.x - self.pad.x) + self.rng.normal(0.0, sigma_world)
        rel_y = (state.y - self.pad.y) + self.rng.normal(0.0, sigma_world)
        return VisionMeasurement(t=t, valid=True, in_fov=True,
                                 rel_x=rel_x, rel_y=rel_y, u=u, v=v,
                                 sigma_world=sigma_world)
