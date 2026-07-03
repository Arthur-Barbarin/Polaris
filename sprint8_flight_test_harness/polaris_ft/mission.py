"""Mission definition: waypoints, path legs, and a geofence.

A mission is an ordered list of (north, east, altitude) waypoints connected by
straight legs. The guidance law (controller.py) follows one leg at a time and
switches to the next when the aircraft passes the leg's half-plane boundary
(the standard Beard & McLain waypoint-switching criterion).

The geofence is an axis-aligned box in the local NE frame plus an altitude
band; a breach at any log sample fails the containment test card.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np


@dataclass(frozen=True)
class Waypoint:
    n: float
    e: float
    h: float


@dataclass
class Geofence:
    n_min: float
    n_max: float
    e_min: float
    e_max: float
    h_min: float
    h_max: float

    def contains(self, n: float, e: float, h: float) -> bool:
        return (
            self.n_min <= n <= self.n_max
            and self.e_min <= e <= self.e_max
            and self.h_min <= h <= self.h_max
        )


@dataclass
class Mission:
    waypoints: List[Waypoint]
    geofence: Geofence
    name: str = "delivery-out-and-back"

    def leg(self, i: int) -> Tuple[Waypoint, Waypoint]:
        return self.waypoints[i], self.waypoints[i + 1]

    @property
    def n_legs(self) -> int:
        return len(self.waypoints) - 1


def default_mission() -> Mission:
    """A short out-and-back delivery-style mission at 100 m AGL.

    ~4 km each way with a dogleg, sized so a fixed-wing at 30 m/s flies it in
    a few minutes — long enough to exercise turns and wind, short enough for a
    fast test campaign.
    """
    wps = [
        Waypoint(0.0, 0.0, 100.0),
        Waypoint(2000.0, 0.0, 120.0),
        Waypoint(4000.0, 1500.0, 120.0),
        Waypoint(4000.0, 3500.0, 100.0),
        Waypoint(1000.0, 3500.0, 100.0),
    ]
    fence = Geofence(
        n_min=-500.0, n_max=4800.0,
        e_min=-800.0, e_max=4300.0,
        h_min=60.0, h_max=180.0,
    )
    return Mission(waypoints=wps, geofence=fence)


def cross_track_error(pn: float, pe: float, wp_from: Waypoint, wp_to: Waypoint) -> float:
    """Signed horizontal cross-track distance from the from->to leg [m].

    Positive means the aircraft is to the left of the path direction.
    """
    path = np.array([wp_to.n - wp_from.n, wp_to.e - wp_from.e])
    norm = np.linalg.norm(path)
    if norm < 1e-6:
        return 0.0
    path_unit = path / norm
    # Left-normal of the path direction (rotate +90 deg in NE plane).
    normal = np.array([-path_unit[1], path_unit[0]])
    rel = np.array([pn - wp_from.n, pe - wp_from.e])
    return float(rel @ normal)


def along_track_fraction(pn: float, pe: float, wp_from: Waypoint, wp_to: Waypoint) -> float:
    """Fraction [0, inf) of the leg travelled; >=1 means past the to-waypoint."""
    path = np.array([wp_to.n - wp_from.n, wp_to.e - wp_from.e])
    norm2 = float(path @ path)
    if norm2 < 1e-6:
        return 1.0
    rel = np.array([pn - wp_from.n, pe - wp_from.e])
    return float((rel @ path) / norm2)
