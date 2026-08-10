"""Encounter kinematics and the geometric primitives DAA Well Clear is built on.

All quantities are SI: positions in metres (local ENU frame, x=East, y=North,
z=Up), velocities in m/s, time in seconds. Aircraft are point masses moving at
constant velocity unless a maneuver is applied (see ``resolution.py``).

The geometric functions here are the exact ones the DO-365 DAA Well Clear
predicate consumes: horizontal range, horizontal closure rate, modified tau,
and horizontal miss distance. Keeping them pure and separately testable is the
point — the well-clear logic in ``wellclear.py`` is nothing more than a set of
comparisons against these.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    """Instantaneous aircraft state in the local ENU frame.

    Position ``(x, y, z)`` in metres, velocity ``(vx, vy, vz)`` in m/s.
    """

    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float

    @property
    def pos(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    @property
    def vel(self) -> tuple[float, float, float]:
        return (self.vx, self.vy, self.vz)

    @property
    def ground_speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    @property
    def heading(self) -> float:
        """Heading in radians, measured clockwise from North (y-axis).

        0 = North, +pi/2 = East. This is the aviation convention.
        """
        return math.atan2(self.vx, self.vy)


@dataclass(frozen=True)
class Encounter:
    """A pairwise encounter: an ownship and one intruder, at t=0."""

    ownship: State
    intruder: State
    encounter_id: int = 0


def propagate(s: State, dt: float) -> State:
    """Advance a state by ``dt`` seconds at constant velocity."""
    return State(
        x=s.x + s.vx * dt,
        y=s.y + s.vy * dt,
        z=s.z + s.vz * dt,
        vx=s.vx,
        vy=s.vy,
        vz=s.vz,
    )


def relative_state(own: State, intr: State) -> tuple[
    tuple[float, float, float], tuple[float, float, float]
]:
    """Return (relative position, relative velocity) of intruder w.r.t. ownship."""
    rp = (intr.x - own.x, intr.y - own.y, intr.z - own.z)
    rv = (intr.vx - own.vx, intr.vy - own.vy, intr.vz - own.vz)
    return rp, rv


def horizontal_range(own: State, intr: State) -> float:
    """Current horizontal (x-y plane) separation in metres."""
    return math.hypot(intr.x - own.x, intr.y - own.y)


def vertical_separation(own: State, intr: State) -> float:
    """Current absolute vertical separation in metres."""
    return abs(intr.z - own.z)


def horizontal_closure_rate(own: State, intr: State) -> float:
    """Range rate ``rdot`` in m/s. Negative when the aircraft are closing.

    ``rdot = (r . v) / |r|`` using the horizontal components only.
    """
    rx, ry = intr.x - own.x, intr.y - own.y
    rvx, rvy = intr.vx - own.vx, intr.vy - own.vy
    r = math.hypot(rx, ry)
    if r == 0.0:
        return 0.0
    return (rx * rvx + ry * rvy) / r


def time_to_cpa(own: State, intr: State) -> float:
    """Time (s) to the horizontal closest point of approach.

    Solves ``d/dt |r_h(t)|^2 = 0`` for the constant-velocity relative motion.
    Returns 0.0 if the aircraft are diverging or co-moving.
    """
    rx, ry = intr.x - own.x, intr.y - own.y
    rvx, rvy = intr.vx - own.vx, intr.vy - own.vy
    v2 = rvx * rvx + rvy * rvy
    if v2 == 0.0:
        return 0.0
    t = -(rx * rvx + ry * rvy) / v2
    return max(t, 0.0)


def horizontal_miss_distance(own: State, intr: State) -> float:
    """Predicted minimum horizontal separation (HMD) under constant velocity."""
    t = time_to_cpa(own, intr)
    o, i = propagate(own, t), propagate(intr, t)
    return horizontal_range(o, i)


def modified_tau(own: State, intr: State, dmod: float) -> float:
    """DO-365 modified tau (s): time-to-go to the DMOD range ring.

    ``tau_mod = -(r^2 - DMOD^2) / (r * rdot)`` for closing geometries
    (``rdot < 0``). Returns ``math.inf`` when not closing — the standard
    convention that a non-closing pair has no finite time-to-encroach.
    """
    r = horizontal_range(own, intr)
    rdot = horizontal_closure_rate(own, intr)
    if rdot >= 0.0:
        return math.inf
    return -(r * r - dmod * dmod) / (r * rdot)


def closest_point_of_approach(
    own: State, intr: State, horizon: float, dt: float = 0.25
) -> tuple[float, float, float]:
    """Sample the trajectory to the true 3-D minimum separation.

    Returns ``(t_min, horizontal_sep, vertical_sep)`` over ``[0, horizon]``.
    Used for scoring outcomes (NMAC / min-sep) rather than for the well-clear
    predicate, which uses the closed-form horizontal CPA above.
    """
    n = max(int(round(horizon / dt)), 1)
    best_t, best_h, best_v = 0.0, horizontal_range(own, intr), vertical_separation(own, intr)
    best_slant = math.hypot(best_h, best_v)
    for k in range(1, n + 1):
        t = k * dt
        o, i = propagate(own, t), propagate(intr, t)
        h = horizontal_range(o, i)
        v = vertical_separation(o, i)
        slant = math.hypot(h, v)
        if slant < best_slant:
            best_slant, best_t, best_h, best_v = slant, t, h, v
    return best_t, best_h, best_v
