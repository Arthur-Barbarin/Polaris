"""Autonomous precision-landing guidance.

A gated descent state machine, closing on the KF estimate (never truth):

  ACQUIRE   high up: null lateral offset; descend only once roughly aligned.
  DESCEND   aligned: descend on an altitude-scheduled sink rate, keep centred.
  FLARE     below flare height: cap sink to a gentle touchdown rate.
  GO_AROUND safety abort: below the decision height, if vision has been lost
            too long OR the estimated lateral error is too large to commit,
            climb away instead of landing (a real flight-test reject).
  LANDED    z <= 0.

The alignment gate ("don't descend until centred") and the decision-height
go-around are the behaviours a flight-test engineer writes cards against.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from .estimator import KFState
from .vehicle import AccelCommand, Multirotor


class Phase(str, Enum):
    ACQUIRE = "ACQUIRE"
    DESCEND = "DESCEND"
    FLARE = "FLARE"
    GO_AROUND = "GO_AROUND"
    LANDED = "LANDED"


@dataclass
class GuidanceGains:
    kp_pos: float = 0.9         # lateral position -> accel [1/s^2]
    kd_vel: float = 1.6         # lateral velocity damping [1/s]
    ki_pos: float = 0.35        # lateral position integral -> rejects steady wind
    i_clamp: float = 10.0       # anti-windup clamp on the position integral [m*s]
    kp_w: float = 1.8           # sink-rate error -> vertical accel [1/s]
    w_touchdown: float = 0.4    # gentle touchdown sink rate [m/s]
    w_descend_gain: float = 0.14  # sink rate per metre of altitude [1/s]
    w_descend_max: float = 3.0  # max sink rate [m/s]
    z_flare: float = 3.0        # flare height [m]
    z_decision: float = 4.0     # decision height [m]
    align_floor: float = 0.30   # min lateral tol to allow descent [m]
    align_slope: float = 0.15   # lateral tol growth per metre altitude [-]
    abort_lateral: float = 1.0  # est lateral error that forces go-around [m]
    vision_timeout: float = 1.0  # max time without vision below decision ht [s]
    climb_rate: float = 2.5     # go-around climb rate [m/s]


class LandingGuidance:
    def __init__(self, mr: Multirotor, gains: GuidanceGains | None = None):
        self.mr = mr
        self.g = gains or GuidanceGains()
        self.phase = Phase.ACQUIRE
        self._last_vision_t = 0.0
        self.go_around_reason = ""
        self._ix = 0.0
        self._iy = 0.0

    def note_vision(self, t: float, valid: bool) -> None:
        if valid:
            self._last_vision_t = t

    def align_tol(self, z: float) -> float:
        return max(self.g.align_floor, self.g.align_slope * z)

    def command(self, est: KFState, t: float, dt: float) -> tuple[AccelCommand, Phase]:
        g = self.g
        px, py, z = est.x[0], est.x[1], est.x[2]
        vx, vy = est.x[3], est.x[4]
        lateral = float(np.hypot(px, py))

        # --- Horizontal: PI + velocity damping. The integral term rejects the
        #     standing offset a steady wind would otherwise leave (no droop). ---
        self._ix = float(np.clip(self._ix + px * dt, -g.i_clamp, g.i_clamp))
        self._iy = float(np.clip(self._iy + py * dt, -g.i_clamp, g.i_clamp))
        ax = -g.kp_pos * px - g.kd_vel * vx - g.ki_pos * self._ix
        ay = -g.kp_pos * py - g.kd_vel * vy - g.ki_pos * self._iy

        # --- Safety: go-around latch below decision height ---
        if self.phase != Phase.GO_AROUND and z <= g.z_decision:
            stale = (t - self._last_vision_t) > g.vision_timeout
            if stale or lateral > g.abort_lateral:
                self.phase = Phase.GO_AROUND
                self.go_around_reason = "vision_lost" if stale else "misaligned"

        if self.phase == Phase.GO_AROUND:
            # Climb away, keep centring.
            az = g.kp_w * (g.climb_rate - est.x[5])
            return AccelCommand(ax=ax, ay=ay, az=az), self.phase

        # --- Vertical sink-rate schedule ---
        # Descent rate is scaled DOWN by misalignment rather than hard-gated to
        # zero, so a small standing offset slows the approach (prioritising
        # centring) without ever trapping the vehicle in a permanent hover.
        if z <= g.z_flare:
            self.phase = Phase.FLARE
            w_cmd = g.w_touchdown
        else:
            tol = self.align_tol(z)
            if lateral <= tol:
                align_factor = 1.0
                self.phase = Phase.DESCEND
            else:
                align_factor = float(np.clip(1.0 - (lateral - tol) / (2 * tol), 0.15, 1.0))
                self.phase = Phase.DESCEND if align_factor > 0.5 else Phase.ACQUIRE
            w_sched = float(np.clip(g.w_descend_gain * z, g.w_touchdown, g.w_descend_max))
            w_cmd = w_sched * align_factor

        # vz target is negative (descending); track it.
        az = g.kp_w * (-w_cmd - est.x[5])
        return AccelCommand(ax=ax, ay=ay, az=az), self.phase
