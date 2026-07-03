"""Cascaded guidance + autopilot for the reduced-order fixed-wing.

Three loops, closed every control tick on the *estimated* state (so the EKF
is genuinely in the loop):

  Lateral   straight-line path following (Beard & McLain eq. 10.8):
            chi_c = chi_path - chi_inf * (2/pi) * atan(k_path * e_xt)
            then a proportional course-hold produces a commanded bank:
            phi_c = clip(k_chi * wrap(chi_c - chi), +/- phi_max)

  Altitude  proportional altitude-hold producing commanded flight-path angle:
            gamma_c = clip(k_h * (h_c - h), +/- gamma_max)

  Airspeed  PI throttle controller:
            throttle = 0.5 + kp*(Va_c - Va) + ki*integral

The controller consumes an *estimate* of (pn, pe, h, Va, chi). Course chi is
the direction of travel over the ground (atan2 of ground velocity), which in
wind differs from heading psi — the guidance law corrects for that.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .mission import Mission, Waypoint, along_track_fraction, cross_track_error
from .vehicle import Airframe, ControlInput, wrap_pi


@dataclass
class Gains:
    k_path: float = 0.02    # cross-track -> course-correction steepness [1/m]
    chi_inf: float = np.radians(60)  # max course approach angle [rad]
    k_chi: float = 1.6      # course error -> bank [rad/rad]
    k_h: float = 0.02       # altitude error -> flight-path angle [rad/m]
    kp_V: float = 0.08      # airspeed P [1/(m/s)]
    ki_V: float = 0.02      # airspeed I [1/(m/s*s)]


@dataclass
class Autopilot:
    mission: Mission
    airframe: Airframe
    gains: Gains
    Va_cmd: float = 30.0

    leg_idx: int = 0
    _int_V: float = 0.0

    def reset(self) -> None:
        self.leg_idx = 0
        self._int_V = 0.0

    def _advance_leg(self, pn: float, pe: float) -> None:
        """Switch to the next leg once past the current to-waypoint."""
        while self.leg_idx < self.mission.n_legs - 1:
            wp_from, wp_to = self.mission.leg(self.leg_idx)
            if along_track_fraction(pn, pe, wp_from, wp_to) >= 1.0:
                self.leg_idx += 1
            else:
                break

    def command(
        self,
        pn: float,
        pe: float,
        h: float,
        Va: float,
        chi: float,
        dt: float,
    ) -> ControlInput:
        """Return control input from the estimated state. `chi` is ground course."""
        self._advance_leg(pn, pe)
        wp_from, wp_to = self.mission.leg(self.leg_idx)

        # --- Lateral: straight-line path following ---
        e_xt = cross_track_error(pn, pe, wp_from, wp_to)
        chi_path = np.arctan2(wp_to.e - wp_from.e, wp_to.n - wp_from.n)
        g = self.gains
        chi_c = chi_path - g.chi_inf * (2.0 / np.pi) * np.arctan(g.k_path * e_xt)
        course_err = wrap_pi(chi_c - chi)
        phi_c = float(np.clip(g.k_chi * course_err, -self.airframe.phi_max, self.airframe.phi_max))

        # --- Altitude hold ---
        h_c = wp_to.h
        gamma_c = float(np.clip(g.k_h * (h_c - h), -self.airframe.gamma_max, self.airframe.gamma_max))

        # --- Airspeed PI throttle ---
        err_V = self.Va_cmd - Va
        self._int_V += err_V * dt
        # Anti-windup clamp on the integrator.
        self._int_V = float(np.clip(self._int_V, -20.0, 20.0))
        throttle = 0.5 + g.kp_V * err_V + g.ki_V * self._int_V
        throttle = float(np.clip(throttle, 0.0, 1.0))

        return ControlInput(phi_c=phi_c, gamma_c=gamma_c, throttle=throttle)
