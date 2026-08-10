"""DAA Well Clear, and the NMAC safety metric — the two volumes that matter.

The thresholds are the published RTCA DO-365 (SC-228) DAA Well Clear (DWC)
values for the "non-cooperative, below FL100" case, plus the ICAO/RTCA Near
Mid-Air Collision (NMAC) definition. Values are stored in SI (metres, seconds)
but declared from their native units so the source is auditable.

    DAA Well Clear (DWC), DO-365:
        DMOD       = 4000 ft   horizontal distance-modification threshold
        HMD_THR    = 4000 ft   horizontal miss-distance threshold
        TAUMOD_THR = 35 s      modified-tau threshold
        ZTHR       = 450 ft    vertical threshold

    NMAC (safety event we are trying to prevent):
        horizontal < 500 ft AND vertical < 100 ft

A pair is in **loss of DAA Well Clear (LoWC)** when the horizontal predicate
AND the vertical predicate hold simultaneously:

    horizontal := (range <= DMOD) OR (HMD <= HMD_THR AND 0 <= tau_mod <= TAUMOD_THR)
    vertical   := |dz| <= ZTHR
    LoWC       := horizontal AND vertical

This is the standard boolean form used in the SC-228 MOPS. NMAC is a strictly
smaller, purely positional volume: every NMAC is a LoWC, but the whole point of
Well Clear is to alert with tens of seconds of margin *before* the NMAC volume
is ever entered.
"""
from __future__ import annotations

from dataclasses import dataclass

from .geometry import (
    State,
    horizontal_range,
    vertical_separation,
    modified_tau,
    horizontal_miss_distance,
    time_to_cpa,
    propagate,
    closest_point_of_approach,
)

FT = 0.3048  # metres per foot


@dataclass(frozen=True)
class WellClearParams:
    """DO-365 DAA Well Clear thresholds (SI)."""

    dmod: float = 4000 * FT        # 1219.2 m
    hmd_thr: float = 4000 * FT     # 1219.2 m
    taumod_thr: float = 35.0       # s
    zthr: float = 450 * FT         # 137.16 m


@dataclass(frozen=True)
class NMACParams:
    """Near Mid-Air Collision volume (SI)."""

    horizontal: float = 500 * FT   # 152.4 m
    vertical: float = 100 * FT     # 30.48 m


DWC = WellClearParams()
NMAC = NMACParams()


def loss_of_well_clear(own: State, intr: State, p: WellClearParams = DWC) -> bool:
    """True if the pair is currently in loss of DAA Well Clear (instantaneous)."""
    r = horizontal_range(own, intr)
    dz = vertical_separation(own, intr)
    tmod = modified_tau(own, intr, p.dmod)
    hmd = horizontal_miss_distance(own, intr)

    horizontal = (r <= p.dmod) or (hmd <= p.hmd_thr and 0.0 <= tmod <= p.taumod_thr)
    vertical = dz <= p.zthr
    return horizontal and vertical


def predicted_lowc(
    own: State, intr: State, lookahead: float, p: WellClearParams = DWC, dt: float = 0.5
) -> tuple[bool, float]:
    """Will the pair lose Well Clear within ``lookahead`` seconds?

    Propagates both aircraft at constant velocity and tests the instantaneous
    LoWC predicate on a fine grid. Returns ``(will_violate, time_to_first_lowc)``;
    ``time`` is ``inf`` if no violation is predicted. This is the detector an
    ownship runs each cycle to decide whether to alert.
    """
    n = max(int(round(lookahead / dt)), 1)
    for k in range(n + 1):
        t = k * dt
        o, i = propagate(own, t), propagate(intr, t)
        if loss_of_well_clear(o, i, p):
            return True, t
    return False, float("inf")


def is_nmac(own: State, intr: State, horizon: float, p: NMACParams = NMAC) -> bool:
    """True if the two trajectories enter the NMAC volume within ``horizon``."""
    _, h, v = closest_point_of_approach(own, intr, horizon)
    return h < p.horizontal and v < p.vertical


def separation_at_cpa(own: State, intr: State, horizon: float) -> tuple[float, float, float]:
    """Convenience wrapper: ``(t_cpa, horizontal_sep, vertical_sep)``."""
    return closest_point_of_approach(own, intr, horizon)
