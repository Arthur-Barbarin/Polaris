"""Resolution advisories: the ownship's closed, evaluated action space.

When the detector predicts a loss of Well Clear, the ownship must pick a
maneuver. This module defines a **small, closed set of candidate maneuvers**
(the action space) and a **receding-horizon selection rule** that scores each
candidate on the geometry it produces and returns the best one.

The design mirrors ACAS-Xu resolution logic — a discrete set of vertical and
horizontal advisories, re-evaluated every cycle — but the "best action" is
chosen here by transparent online scoring rather than a pre-computed lookup
table. Every candidate is flown forward against the (constant-velocity)
intruder and scored on the minimum separation it yields and whether it clears
the Well Clear volume. Nothing about the choice is hidden: the score is a
geometric quantity you can recompute by hand.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import State
from .wellclear import WellClearParams, DWC, loss_of_well_clear


@dataclass(frozen=True)
class Maneuver:
    """A constant-control advisory applied to the ownship.

    ``turn_rate`` is in rad/s (positive = turn right / clockwise). If
    ``sets_vertical`` is True the maneuver commands ``vertical_rate`` (m/s,
    positive = climb); otherwise the ownship keeps its current vertical rate.
    ``priority`` breaks ties deterministically (lower = preferred), encoding a
    mild preference for the least-disruptive advisory.
    """

    name: str
    turn_rate: float = 0.0
    vertical_rate: float = 0.0
    sets_vertical: bool = False
    priority: int = 0


_STD_TURN = math.radians(3.0)   # 3 deg/s — ICAO standard rate, halved band
_CLIMB = 2.54                   # m/s ≈ 500 ft/min

#: The closed candidate set the selector chooses from each cycle.
MANEUVER_SET: tuple[Maneuver, ...] = (
    Maneuver("MAINTAIN", 0.0, 0.0, False, priority=0),
    Maneuver("CLIMB", 0.0, +_CLIMB, True, priority=1),
    Maneuver("DESCEND", 0.0, -_CLIMB, True, priority=1),
    Maneuver("TURN_RIGHT", +_STD_TURN, 0.0, False, priority=2),
    Maneuver("TURN_LEFT", -_STD_TURN, 0.0, False, priority=2),
)


@dataclass(frozen=True)
class ResolutionParams:
    """Horizon and cadence for RA evaluation and execution."""

    lookahead: float = 40.0   # s — how far ahead each candidate is scored
    dt: float = 0.5           # s — integration step for scoring


def apply_maneuver(s: State, m: Maneuver, dt: float) -> State:
    """Advance a state one step of ``dt`` under maneuver ``m``.

    Horizontal ground speed is preserved; the heading rotates at the maneuver's
    turn rate and the vertical rate is set if the maneuver commands it.
    """
    gs = s.ground_speed
    if gs > 0.0 and m.turn_rate != 0.0:
        hdg = math.atan2(s.vx, s.vy) + m.turn_rate * dt
        vx, vy = gs * math.sin(hdg), gs * math.cos(hdg)
    else:
        vx, vy = s.vx, s.vy
    vz = m.vertical_rate if m.sets_vertical else s.vz
    return State(
        x=s.x + vx * dt,
        y=s.y + vy * dt,
        z=s.z + vz * dt,
        vx=vx,
        vy=vy,
        vz=vz,
    )


def _fly_ownship(s: State, m: Maneuver, horizon: float, dt: float) -> list[State]:
    """Trajectory of the ownship under a fixed maneuver over ``[0, horizon]``."""
    out = [s]
    n = max(int(round(horizon / dt)), 1)
    cur = s
    for _ in range(n):
        cur = apply_maneuver(cur, m, dt)
        out.append(cur)
    return out


def _fly_intruder(s: State, horizon: float, dt: float) -> list[State]:
    out = [s]
    n = max(int(round(horizon / dt)), 1)
    cur = s
    for _ in range(n):
        cur = State(cur.x + cur.vx * dt, cur.y + cur.vy * dt, cur.z + cur.vz * dt,
                    cur.vx, cur.vy, cur.vz)
        out.append(cur)
    return out


def _score(own_traj: list[State], intr_traj: list[State], p: WellClearParams) -> tuple[bool, float]:
    """Score a candidate: ``(clears_well_clear, min_slant_separation_m)``."""
    clears = True
    min_slant = math.inf
    for o, i in zip(own_traj, intr_traj):
        h = math.hypot(i.x - o.x, i.y - o.y)
        v = abs(i.z - o.z)
        slant = math.hypot(h, v)
        if slant < min_slant:
            min_slant = slant
        if loss_of_well_clear(o, i, p):
            clears = False
    return clears, min_slant


def select_ra(
    own: State,
    intr: State,
    params: ResolutionParams = ResolutionParams(),
    wc: WellClearParams = DWC,
) -> tuple[Maneuver, float]:
    """Choose the best resolution advisory for the current geometry.

    Every maneuver in ``MANEUVER_SET`` is flown forward against the
    constant-velocity intruder and scored. The winner is the candidate that
    (1) clears the Well Clear volume if any candidate can, then (2) maximises
    the minimum slant separation, with ``priority`` as a deterministic
    tie-break. Returns ``(maneuver, predicted_min_separation_m)``.
    """
    intr_traj = _fly_intruder(intr, params.lookahead, params.dt)
    best: tuple[Maneuver, float] | None = None
    best_key: tuple[int, float, int] | None = None
    for m in MANEUVER_SET:
        own_traj = _fly_ownship(own, m, params.lookahead, params.dt)
        clears, min_slant = _score(own_traj, intr_traj, wc)
        # sort key: prefer clears (1>0), then larger min_slant, then lower priority
        key = (1 if clears else 0, min_slant, -m.priority)
        if best_key is None or key > best_key:
            best_key, best = key, (m, min_slant)
    assert best is not None
    return best
