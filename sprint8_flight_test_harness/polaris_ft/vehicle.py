"""Reduced-order fixed-wing UAV dynamics.

This is a *kinematic guidance-level* model with first-order autopilot inner
loops, in the style of Beard & McLain, "Small Unmanned Aircraft: Theory and
Practice" (2012), Ch. 9 (autopilot) and Ch. 10 (path following). It is NOT a
full 6-DOF aerodynamic model — there are no aero coefficients, no actuator
surface deflections, and no stall model. What it *does* capture, faithfully,
is the closed-loop behaviour a guidance/flight-test engineer cares about:

  * airspeed vs ground speed in wind (crab angle, cross-track drift),
  * coordinated-turn heading kinematics (psi_dot = g/V * tan(phi)),
  * bank / flight-path / airspeed inner loops as rate-limited first-order lags,
  * hard limits on bank angle, flight-path angle, and throttle authority.

State vector (SI units, radians):
    pn      north position   [m]
    pe      east position    [m]
    h       altitude         [m]
    Va      airspeed         [m/s]   (through the air mass)
    psi     heading          [rad]   (direction the nose points)
    gamma   air-mass flight-path angle [rad]
    phi     bank angle       [rad]

Controls (produced by the autopilot in controller.py):
    phi_c     commanded bank angle       [rad]
    gamma_c   commanded flight-path angle[rad]
    throttle  in [0, 1]

Wind enters as a steady + gust vector (Wn, We) [m/s]; ground velocity is the
air-relative velocity plus wind, so all position integration and cross-track
error are computed in the ground frame.

Reference constants for the default airframe are taken from Beard & McLain's
"Aerosonde"-class small UAV (Va ~ 25-35 m/s cruise, bank limit ~45 deg).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

G = 9.80665  # m/s^2, standard gravity


@dataclass(frozen=True)
class Airframe:
    """Static parameters for a reduced-order fixed-wing UAV.

    Defaults model an Aerosonde-class small UAV (Beard & McLain, App. E),
    which is a reasonable stand-in for a small fixed-wing delivery aircraft
    of the Zipline-P2 class (fixed-wing, cruise ~30 m/s).
    """

    name: str = "aerosonde-class"
    Va_cruise: float = 30.0          # nominal cruise airspeed [m/s]
    Va_min: float = 18.0             # ~stall-limited minimum airspeed [m/s]
    Va_max: float = 42.0             # never-exceed airspeed [m/s]
    phi_max: float = np.radians(45)  # bank limit [rad]
    gamma_max: float = np.radians(15)  # climb/descent limit [rad]
    # Inner-loop time constants (first-order autopilot response).
    tau_phi: float = 0.35            # roll [s]
    tau_gamma: float = 1.2           # flight-path [s]
    tau_Va: float = 4.0             # airspeed/throttle -> speed [s]
    # Throttle authority: max accel at full throttle, max decel at idle [m/s^2].
    accel_max: float = 2.5
    decel_max: float = 2.0


@dataclass
class VehicleState:
    pn: float = 0.0
    pe: float = 0.0
    h: float = 100.0
    Va: float = 30.0
    psi: float = 0.0
    gamma: float = 0.0
    phi: float = 0.0

    def copy(self) -> "VehicleState":
        return replace(self)


@dataclass
class ControlInput:
    phi_c: float = 0.0
    gamma_c: float = 0.0
    throttle: float = 0.5


@dataclass
class Wind:
    """Steady wind plus an optional time-varying gust callback.

    Wn, We are the steady components [m/s] (wind blowing *toward* north/east).
    `gust(t)` returns an additional (dWn, dWe) tuple; default is no gust.
    """

    Wn: float = 0.0
    We: float = 0.0
    gust: object = None  # Optional[Callable[[float], tuple[float, float]]]

    def sample(self, t: float) -> tuple[float, float]:
        wn, we = self.Wn, self.We
        if self.gust is not None:
            dn, de = self.gust(t)
            wn += dn
            we += de
        return wn, we


@dataclass
class Actuator:
    """Control-effectiveness multipliers, used for actuator-fault injection.

    A healthy vehicle has all multipliers = 1.0. Reduced roll authority
    (aileron loss) drops `roll_eff`; reduced pitch authority drops
    `pitch_eff`; a throttle fault drops `thr_eff`.
    """

    roll_eff: float = 1.0
    pitch_eff: float = 1.0
    thr_eff: float = 1.0


def derivatives(
    state: VehicleState,
    ctrl: ControlInput,
    wind: Wind,
    t: float,
    airframe: Airframe,
    act: Actuator,
) -> np.ndarray:
    """Continuous-time state derivative d/dt [pn, pe, h, Va, psi, gamma, phi]."""
    af = airframe

    # --- Inner-loop responses (first-order lags toward commanded values) ---
    phi_c = float(np.clip(ctrl.phi_c, -af.phi_max, af.phi_max)) * act.roll_eff
    gamma_c = float(np.clip(ctrl.gamma_c, -af.gamma_max, af.gamma_max)) * act.pitch_eff
    phi_dot = (phi_c - state.phi) / af.tau_phi
    gamma_dot = (gamma_c - state.gamma) / af.tau_gamma

    # Airspeed: throttle in [0,1] maps to accel in [-decel_max, +accel_max],
    # then a first-order lag pulls Va toward the throttle-implied trim speed.
    thr = float(np.clip(ctrl.throttle, 0.0, 1.0)) * act.thr_eff
    accel_cmd = (2.0 * thr - 1.0)
    accel_cmd = accel_cmd * (af.accel_max if accel_cmd >= 0 else af.decel_max)
    Va_dot = accel_cmd - (state.Va - af.Va_cruise) / af.tau_Va

    # --- Coordinated-turn heading kinematics ---
    Va = max(state.Va, 1.0)  # guard against divide-by-zero
    psi_dot = (G / Va) * np.tan(state.phi)

    # --- Air-relative velocity, then add wind for ground velocity ---
    cg = np.cos(state.gamma)
    va_n = state.Va * np.cos(state.psi) * cg
    va_e = state.Va * np.sin(state.psi) * cg
    va_d = state.Va * np.sin(state.gamma)  # vertical (up positive)

    wn, we = wind.sample(t)
    vg_n = va_n + wn
    vg_e = va_e + we

    pn_dot = vg_n
    pe_dot = vg_e
    h_dot = va_d  # vertical wind neglected

    return np.array(
        [pn_dot, pe_dot, h_dot, Va_dot, psi_dot, gamma_dot, phi_dot], dtype=float
    )


def step_rk4(
    state: VehicleState,
    ctrl: ControlInput,
    wind: Wind,
    t: float,
    dt: float,
    airframe: Airframe,
    act: Actuator,
) -> VehicleState:
    """Advance the vehicle one step with classic RK4."""

    def f(s: VehicleState, tt: float) -> np.ndarray:
        return derivatives(s, ctrl, wind, tt, airframe, act)

    def add(s: VehicleState, d: np.ndarray, k: float) -> VehicleState:
        return VehicleState(
            pn=s.pn + k * d[0],
            pe=s.pe + k * d[1],
            h=s.h + k * d[2],
            Va=s.Va + k * d[3],
            psi=s.psi + k * d[4],
            gamma=s.gamma + k * d[5],
            phi=s.phi + k * d[6],
        )

    k1 = f(state, t)
    k2 = f(add(state, k1, dt / 2), t + dt / 2)
    k3 = f(add(state, k2, dt / 2), t + dt / 2)
    k4 = f(add(state, k3, dt), t + dt)
    incr = (k1 + 2 * k2 + 2 * k3 + k4) / 6.0
    nxt = add(state, incr, dt)

    # Enforce airspeed envelope + wrap heading.
    nxt.Va = float(np.clip(nxt.Va, airframe.Va_min * 0.6, airframe.Va_max * 1.2))
    nxt.psi = wrap_pi(nxt.psi)
    nxt.phi = float(np.clip(nxt.phi, -airframe.phi_max, airframe.phi_max))
    nxt.gamma = float(np.clip(nxt.gamma, -airframe.gamma_max, airframe.gamma_max))
    return nxt


def wrap_pi(angle: float) -> float:
    """Wrap an angle to (-pi, pi]."""
    return (angle + np.pi) % (2 * np.pi) - np.pi
