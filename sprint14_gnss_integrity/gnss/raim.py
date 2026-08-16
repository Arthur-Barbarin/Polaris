"""RAIM: least-squares solution, residual fault detection, exclusion, and
protection levels.

Receiver Autonomous Integrity Monitoring is three ideas stacked on the
least-squares position solution:

1. **Detection.** The residual (parity) vector ``w = (I - P)z`` has a
   sum-of-squares that, when the receiver is healthy, is chi-square with
   ``n - 4`` degrees of freedom. A single satellite bias inflates it; compare
   ``SSE/σ²`` to a chi-square threshold set by the allowed false-alarm rate.

2. **Exclusion.** If a fault is detected, drop each satellite in turn and
   re-solve; the subset whose removal collapses the residual is the faulted
   satellite. Exclude it and recompute.

3. **Protection level.** Independent of any actual measurement, the geometry
   fixes how large an *undetected* bias could grow the horizontal position
   error — the Horizontal Protection Level (HPL). If HPL exceeds the operation's
   Horizontal Alert Limit (HAL), integrity cannot be assured and the fix is
   declared *unavailable* rather than used unsafely.

The clean separation matters: detection and exclusion look at the data;
availability (HPL vs HAL) is a property of the geometry alone and is decided
*before* trusting the fix.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from .chi2 import chi2_ppf, ncx2_pbias
from .measurements import Scenario


@lru_cache(maxsize=None)
def _pbias(dof: int, pfa: float, pmd: float) -> float:
    """Cached RAIM pbias — depends only on dof and the two probabilities."""
    thr = chi2_ppf(1.0 - pfa, dof)
    return ncx2_pbias(dof, thr, pmd)


@dataclass
class LSSolution:
    dx: np.ndarray        # estimated [E, N, U, clock] error, metres
    residual: np.ndarray  # parity vector w, metres
    sse: float            # residual sum of squares
    dof: int              # n - 4

    @property
    def horizontal(self) -> np.ndarray:
        return self.dx[:2]


def ls_solve(H: np.ndarray, z: np.ndarray) -> LSSolution:
    """Ordinary least-squares GNSS solution and its residual."""
    A = np.linalg.inv(H.T @ H) @ H.T           # 4 x n estimator
    dx = A @ z
    w = z - H @ dx
    sse = float(w @ w)
    return LSSolution(dx=dx, residual=w, sse=sse, dof=H.shape[0] - 4)


@dataclass
class RaimParams:
    pfa: float = 1.0e-3       # per-epoch false-alarm probability
    pmd: float = 1.0e-3       # missed-detection probability for HPL sizing
    hal: float = 200.0        # m, Horizontal Alert Limit for the operation


def detection_threshold(sigma: float, dof: int, pfa: float) -> float:
    """SSE threshold (metres²) for the configured false-alarm probability."""
    return sigma * sigma * chi2_ppf(1.0 - pfa, dof)


@dataclass
class DetectionResult:
    detected: bool
    sse: float
    threshold: float
    dof: int


def detect(scn: Scenario, params: RaimParams = RaimParams()) -> DetectionResult:
    """Fault detection: is the residual sum-of-squares beyond threshold?"""
    sol = ls_solve(scn.H, scn.z)
    if sol.dof < 1:
        return DetectionResult(False, sol.sse, float("inf"), sol.dof)
    thr = detection_threshold(scn.sigma, sol.dof, params.pfa)
    return DetectionResult(sol.sse > thr, sol.sse, thr, sol.dof)


@dataclass
class ExclusionResult:
    detected: bool
    excluded_sv: int | None
    correct: bool | None       # matched the injected fault (if any)
    sol_before: LSSolution
    sol_after: LSSolution | None


def exclude(scn: Scenario, params: RaimParams = RaimParams()) -> ExclusionResult:
    """Detect, then if faulted, identify and remove the offending satellite."""
    det = detect(scn, params)
    before = ls_solve(scn.H, scn.z)
    if not det.detected:
        return ExclusionResult(False, None, None, before, None)

    n = scn.H.shape[0]
    if n - 1 - 4 < 1:  # need residual redundancy after removing one
        return ExclusionResult(True, None, None, before, None)

    best_sv, best_sse, best_sol = None, float("inf"), None
    for i in range(n):
        keep = [j for j in range(n) if j != i]
        sol_i = ls_solve(scn.H[keep], scn.z[keep])
        if sol_i.sse < best_sse:
            best_sse, best_sv, best_sol = sol_i.sse, i, sol_i

    fault_sv = scn.meta.get("fault_sv")
    correct = (best_sv == fault_sv) if fault_sv is not None else None
    return ExclusionResult(True, best_sv, correct, before, best_sol)


def horizontal_slopes(H: np.ndarray) -> np.ndarray:
    """Per-satellite horizontal slope: horizontal error growth per unit residual."""
    A = np.linalg.inv(H.T @ H) @ H.T          # 4 x n
    P = H @ A                                  # hat matrix
    S = np.eye(H.shape[0]) - P                 # residual projector
    slopes = np.zeros(H.shape[0])
    for i in range(H.shape[0]):
        sii = S[i, i]
        if sii <= 1e-9:
            slopes[i] = np.inf
            continue
        horiz = A[0, i] ** 2 + A[1, i] ** 2
        slopes[i] = np.sqrt(horiz / sii)
    return slopes


@dataclass
class ProtectionLevel:
    hpl: float
    slope_max: float
    pbias: float
    available: bool


def protection_level(
    H: np.ndarray, sigma: float, params: RaimParams = RaimParams()
) -> ProtectionLevel:
    """Horizontal Protection Level and the availability decision (HPL vs HAL)."""
    dof = H.shape[0] - 4
    if dof < 1:
        return ProtectionLevel(float("inf"), float("inf"), float("nan"), False)
    pbias = _pbias(dof, params.pfa, params.pmd)
    slopes = horizontal_slopes(H)
    slope_max = float(np.max(slopes))
    hpl = slope_max * sigma * pbias
    return ProtectionLevel(hpl=hpl, slope_max=slope_max, pbias=pbias,
                           available=hpl < params.hal)
