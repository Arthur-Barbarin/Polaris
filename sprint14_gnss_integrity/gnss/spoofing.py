"""Spoofing and jamming detection — the layer RAIM cannot provide.

Residual-based RAIM is blind to a *coordinated* spoof: if every pseudorange is
shifted by a self-consistent amount, the residual stays noise-sized and the
solution walks off undetected. Catching that needs information RAIM never
looks at:

* **C/N0 signature.** A single spoofing transmitter drives every tracked signal
  to a similar, unusually high carrier-to-noise ratio. Genuine satellites show
  an elevation-dependent *spread*; a flat, high C/N0 profile is anomalous.
* **Position innovation.** The spoofed solution jumps relative to an independent
  position prior (previous epoch propagated, or an inertial estimate). A
  Mahalanobis test on that jump, using the combined solution+prior covariance,
  flags a discontinuity no honest geometry would produce.

Jamming is the simpler cousin: broadband interference depresses C/N0 across the
whole band, which a mean-C/N0 floor detects directly.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .chi2 import chi2_ppf
from .measurements import Scenario, MeasurementParams
from .raim import RaimParams, detect, ls_solve


@dataclass
class SpoofParams:
    cn0_high: float = 48.0        # dB-Hz, mean above which power looks spoofed
    cn0_std_low: float = 1.2      # dB-Hz, spread below which profile looks too flat
    innovation_pfa: float = 1.0e-4  # false-alarm prob for the position-jump test


@dataclass
class IntegrityStatus:
    raim_detected: bool
    jam_flag: bool
    cn0_spoof_flag: bool
    innovation_flag: bool
    mean_cn0: float
    cn0_std: float
    mahalanobis: float

    @property
    def spoof_flag(self) -> bool:
        return self.cn0_spoof_flag or self.innovation_flag

    @property
    def trustworthy(self) -> bool:
        """The fix may be used only if nothing tripped."""
        return not (self.raim_detected or self.jam_flag or self.spoof_flag)


def jamming_flag(scn: Scenario, mp: MeasurementParams = MeasurementParams()) -> bool:
    return float(np.mean(scn.cn0)) < mp.cn0_alert


def cn0_spoof_flag(scn: Scenario, sp: SpoofParams = SpoofParams()) -> bool:
    cn0 = scn.cn0
    return float(np.mean(cn0)) > sp.cn0_high and float(np.std(cn0)) < sp.cn0_std_low


def innovation_mahalanobis(scn: Scenario, raim: RaimParams = RaimParams()) -> float:
    """Squared Mahalanobis distance of the solution from the position prior."""
    sol = ls_solve(scn.H, scn.z)
    Q = np.linalg.inv(scn.H.T @ scn.H)[:2, :2] * (scn.sigma ** 2)
    prior_cov = (scn.prior_sigma ** 2) * np.eye(2)
    S = Q + prior_cov
    innov = sol.horizontal - scn.prior_pos
    return float(innov @ np.linalg.solve(S, innov))


def innovation_flag(scn: Scenario, raim: RaimParams = RaimParams(),
                    sp: SpoofParams = SpoofParams()) -> bool:
    d2 = innovation_mahalanobis(scn, raim)
    return d2 > chi2_ppf(1.0 - sp.innovation_pfa, 2)


def screen(
    scn: Scenario,
    raim: RaimParams = RaimParams(),
    sp: SpoofParams = SpoofParams(),
    mp: MeasurementParams = MeasurementParams(),
) -> IntegrityStatus:
    """Run the full integrity screen: RAIM + jamming + spoofing."""
    det = detect(scn, raim)
    cn0 = scn.cn0
    return IntegrityStatus(
        raim_detected=det.detected,
        jam_flag=jamming_flag(scn, mp),
        cn0_spoof_flag=cn0_spoof_flag(scn, sp),
        innovation_flag=innovation_flag(scn, raim, sp),
        mean_cn0=float(np.mean(cn0)),
        cn0_std=float(np.std(cn0)),
        mahalanobis=innovation_mahalanobis(scn, raim),
    )
