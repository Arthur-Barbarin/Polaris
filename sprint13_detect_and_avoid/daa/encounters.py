"""Seeded Monte-Carlo encounter generation.

Encounters are constructed *from the geometry we want at the closest point of
approach*, not by dropping aircraft randomly and hoping they conflict. For each
sample we choose a horizontal miss distance (HMD), a vertical offset, a time to
CPA, and both speeds/headings, then solve for the intruder's initial position
so that a no-maneuver ownship would pass the intruder at exactly that HMD and
vertical offset.

This makes the encounter set a controlled stress field: a known, tunable
fraction are genuine NMAC geometries, the rest are near-misses and safe passes.
Because the whole thing is driven by a single ``numpy`` seed, an encounter set
is byte-for-byte reproducible.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .geometry import State, Encounter


@dataclass(frozen=True)
class EncounterParams:
    """Sampling ranges for the encounter set (SI units)."""

    own_speed: tuple[float, float] = (25.0, 55.0)      # m/s
    intruder_speed: tuple[float, float] = (25.0, 75.0)  # m/s
    t_cpa: tuple[float, float] = (30.0, 75.0)           # s
    hmd: tuple[float, float] = (0.0, 1500.0)            # m (miss distance at CPA)
    vertical: tuple[float, float] = (-200.0, 200.0)     # m (offset at CPA)
    # intruder heading sampled in [60, 300] deg to bias toward closing geometries
    intruder_heading_deg: tuple[float, float] = (60.0, 300.0)
    min_closure: float = 8.0                            # m/s — reject near-parallel pairs


def _state_from(speed: float, heading: float, pos: tuple[float, float, float]) -> State:
    vx = speed * math.sin(heading)
    vy = speed * math.cos(heading)
    return State(pos[0], pos[1], pos[2], vx, vy, 0.0)


def sample_encounter(rng: np.random.Generator, p: EncounterParams, eid: int = 0) -> Encounter:
    """Draw a single encounter with a prescribed CPA geometry."""
    for _ in range(64):  # resample until a valid closing geometry is found
        vo = rng.uniform(*p.own_speed)
        vi = rng.uniform(*p.intruder_speed)
        tcpa = rng.uniform(*p.t_cpa)
        hmd = rng.uniform(*p.hmd)
        dz = rng.uniform(*p.vertical)
        psi = math.radians(rng.uniform(*p.intruder_heading_deg))

        # Ownship at origin heading North; intruder heading psi.
        own = State(0.0, 0.0, 0.0, vo * math.sin(0.0), vo * math.cos(0.0), 0.0)
        ivx, ivy = vi * math.sin(psi), vi * math.cos(psi)

        # Relative (horizontal) velocity of intruder w.r.t. ownship.
        rvx, rvy = ivx - own.vx, ivy - own.vy
        closure = math.hypot(rvx, rvy)
        if closure < p.min_closure:
            continue

        # Unit vector perpendicular to relative velocity: place CPA offset here.
        nx, ny = -rvy / closure, rvx / closure
        sign = 1.0 if rng.random() < 0.5 else -1.0
        # Relative position at CPA (perpendicular, magnitude = HMD).
        rcx, rcy = sign * hmd * nx, sign * hmd * ny
        # Back out relative position at t=0, then intruder absolute position.
        r0x, r0y = rcx - rvx * tcpa, rcy - rvy * tcpa
        intr = State(r0x, r0y, dz, ivx, ivy, 0.0)
        return Encounter(ownship=own, intruder=intr, encounter_id=eid)

    raise RuntimeError("could not sample a valid closing encounter")


def encounter_set(n: int, seed: int = 0, p: EncounterParams = EncounterParams()) -> list[Encounter]:
    """Generate ``n`` reproducible encounters from ``seed``."""
    rng = np.random.default_rng(seed)
    return [sample_encounter(rng, p, eid=i) for i in range(n)]
