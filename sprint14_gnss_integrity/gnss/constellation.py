"""Satellite geometry: line-of-sight vectors, the geometry matrix, and DOP.

Everything the estimator and RAIM need about *where the satellites are* lives
here and nowhere else. Satellites are described by azimuth and elevation as seen
from the receiver (the only thing that matters for the linearized GNSS
solution); the geometry matrix and the dilution-of-precision values fall out of
those angles.

Frame is local **ENU** (East, North, Up), metres. The unit line-of-sight to a
satellite at azimuth ``az`` (from North, clockwise) and elevation ``el`` is
``(cos el·sin az, cos el·cos az, sin el)``. Each geometry-matrix row is the
negative of that LOS plus a 1 for the receiver clock — the standard GNSS
observation partials.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Satellite:
    """A satellite as seen from the receiver."""

    az: float      # azimuth, radians (from North, clockwise)
    el: float      # elevation, radians (above horizon)
    cn0: float = 45.0   # carrier-to-noise density, dB-Hz
    svid: int = 0

    @property
    def los(self) -> tuple[float, float, float]:
        ce = math.cos(self.el)
        return (ce * math.sin(self.az), ce * math.cos(self.az), math.sin(self.el))


def geometry_matrix(sats: list[Satellite]) -> np.ndarray:
    """Return the ``n x 4`` geometry (design) matrix H = [-LOS | 1]."""
    rows = []
    for s in sats:
        ex, en, eu = s.los
        rows.append([-ex, -en, -eu, 1.0])
    return np.asarray(rows, dtype=float)


def cofactor(H: np.ndarray) -> np.ndarray:
    """Return the unweighted cofactor matrix ``(HᵀH)⁻¹`` (4x4)."""
    return np.linalg.inv(H.T @ H)


def dop(H: np.ndarray) -> dict[str, float]:
    """Dilution-of-precision values from the geometry matrix.

    Order of the state is [East, North, Up, clock], so the diagonal of the
    cofactor matrix gives the E/N/U/T variances (in units of measurement
    variance).
    """
    Q = cofactor(H)
    qe, qn, qu, qt = Q[0, 0], Q[1, 1], Q[2, 2], Q[3, 3]
    return {
        "HDOP": math.sqrt(qe + qn),
        "VDOP": math.sqrt(qu),
        "PDOP": math.sqrt(qe + qn + qu),
        "TDOP": math.sqrt(qt),
        "GDOP": math.sqrt(qe + qn + qu + qt),
    }


def cn0_from_elevation(el: float, rng: np.random.Generator | None = None) -> float:
    """A plausible clear-sky C/N0: higher for higher-elevation satellites."""
    base = 37.0 + 10.0 * math.sin(el)
    if rng is not None:
        base += rng.normal(0.0, 0.6)
    return base


def random_constellation(
    rng: np.random.Generator, n: int, mask_deg: float = 7.5
) -> list[Satellite]:
    """Sample ``n`` satellites above the elevation mask with a realistic sky spread.

    Elevation is drawn so the density is roughly uniform over the visible
    hemisphere (more satellites are low in the sky than at zenith), and azimuth
    is uniform. Geometry is redrawn by the caller per scenario via the seed.
    """
    mask = math.radians(mask_deg)
    sats: list[Satellite] = []
    for i in range(n):
        az = rng.uniform(0.0, 2.0 * math.pi)
        # sin(el) uniform in [sin(mask), 1] -> hemisphere-uniform elevation density
        sin_el = rng.uniform(math.sin(mask), 1.0)
        el = math.asin(sin_el)
        sats.append(Satellite(az=az, el=el, cn0=cn0_from_elevation(el, rng), svid=i + 1))
    return sats
