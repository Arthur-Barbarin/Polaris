"""Pseudorange measurement model and seeded threat scenarios.

The linearized GNSS observation is ``z = H·Δx + ε`` where ``Δx`` is the 4-vector
[East, North, Up, clock] error, ``H`` is the geometry matrix, and ``ε`` is
zero-mean Gaussian receiver noise with standard deviation ``sigma`` (the user
range accuracy, URA). Truth is ``Δx = 0``; a healthy receiver sees only noise.

Four scenario builders inject the threats a GNSS integrity monitor exists to
catch, each fully determined by a ``numpy`` seed:

* ``nominal``       — fault-free noise only.
* ``single_fault``  — a step bias on one satellite (the classic RAIM target).
* ``spoof``         — a *coordinated* bias across all satellites engineered to
  move the position solution while keeping the residuals noise-sized, so
  residual-based RAIM is blind to it by construction.
* ``jamming``       — depressed C/N0 and inflated noise across the band.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .constellation import Satellite, geometry_matrix, random_constellation


@dataclass(frozen=True)
class MeasurementParams:
    n_sats: tuple[int, int] = (8, 11)       # inclusive range of visible satellites
    sigma_ura: float = 5.0                  # m, nominal pseudorange noise (1 sigma)
    mask_deg: float = 7.5
    prior_sigma: float = 15.0               # m, 1-sigma of the independent position prior
    jam_cn0_drop: float = 15.0              # dB-Hz reduction under jamming
    jam_sigma_mult: float = 3.5             # noise inflation under jamming
    cn0_alert: float = 34.0                 # dB-Hz mean below which jamming is flagged


@dataclass
class Scenario:
    """One epoch of measurements plus the ground truth of what was injected."""

    kind: str
    sats: list[Satellite]
    H: np.ndarray
    sigma: float
    z: np.ndarray                 # measurement (residual-space) vector, metres
    truth_offset: np.ndarray      # true horizontal position offset (E, N), metres
    prior_pos: np.ndarray         # independent prior position (E, N), metres
    prior_sigma: float
    meta: dict = field(default_factory=dict)

    @property
    def cn0(self) -> np.ndarray:
        return np.array([s.cn0 for s in self.sats])


def _draw_constellation(rng: np.random.Generator, p: MeasurementParams) -> list[Satellite]:
    n = int(rng.integers(p.n_sats[0], p.n_sats[1] + 1))
    return random_constellation(rng, n, p.mask_deg)


def nominal(rng: np.random.Generator, p: MeasurementParams = MeasurementParams()) -> Scenario:
    sats = _draw_constellation(rng, p)
    H = geometry_matrix(sats)
    z = rng.normal(0.0, p.sigma_ura, size=len(sats))
    return Scenario(
        kind="nominal", sats=sats, H=H, sigma=p.sigma_ura, z=z,
        truth_offset=np.zeros(2), prior_pos=np.zeros(2), prior_sigma=p.prior_sigma,
        meta={},
    )


def single_fault(
    rng: np.random.Generator,
    p: MeasurementParams = MeasurementParams(),
    bias_range: tuple[float, float] = (30.0, 150.0),
) -> Scenario:
    s = nominal(rng, p)
    k = int(rng.integers(0, len(s.sats)))
    bias = float(rng.uniform(*bias_range)) * (1.0 if rng.random() < 0.5 else -1.0)
    z = s.z.copy()
    z[k] += bias
    s.z = z
    s.kind = "single_fault"
    s.meta = {"fault_sv": k, "fault_bias": bias}
    return s


def spoof(
    rng: np.random.Generator,
    p: MeasurementParams = MeasurementParams(),
    offset_range: tuple[float, float] = (40.0, 200.0),
) -> Scenario:
    """A coordinated spoof: shift the solution by a target offset, residual-clean."""
    s = nominal(rng, p)
    ang = rng.uniform(0.0, 2.0 * np.pi)
    mag = float(rng.uniform(*offset_range))
    dp = np.array([mag * np.cos(ang), mag * np.sin(ang)])      # horizontal offset
    dclk = float(rng.uniform(-30.0, 30.0))
    # Build the full 4-state the spoofer imposes and add H @ state to every range.
    dx = np.array([dp[0], dp[1], 0.0, dclk])
    s.z = s.z + s.H @ dx
    # Spoofed signals share a transmitter: unnaturally high, uniform C/N0.
    spoof_cn0 = float(rng.uniform(49.0, 52.0))
    s.sats = [Satellite(sv.az, sv.el, spoof_cn0 + float(rng.normal(0, 0.2)), sv.svid)
              for sv in s.sats]
    s.kind = "spoof"
    # True position is still the origin; the spoof makes the receiver *compute*
    # an offset of ~dp. That induced solution error is the hazard, recorded in meta.
    s.truth_offset = np.zeros(2)
    s.meta = {"spoof_offset": mag, "spoof_clock": dclk}
    return s


def jamming(rng: np.random.Generator, p: MeasurementParams = MeasurementParams()) -> Scenario:
    s = nominal(rng, p)
    sigma_j = p.sigma_ura * p.jam_sigma_mult
    s.z = rng.normal(0.0, sigma_j, size=len(s.sats))
    s.sigma = sigma_j
    s.sats = [Satellite(sv.az, sv.el, sv.cn0 - p.jam_cn0_drop, sv.svid) for sv in s.sats]
    s.kind = "jamming"
    s.meta = {"jammed": True}
    return s
