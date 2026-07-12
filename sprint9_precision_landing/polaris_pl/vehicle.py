"""Multirotor translational dynamics for precision-landing guidance.

A quadrotor is modelled at the *guidance* level as an acceleration-limited
double integrator in a local frame centred on the landing pad:

    state  = [x, y, z, vx, vy, vz]     position [m] + velocity [m/s]
    input  = commanded acceleration [ax, ay, az] [m/s^2]

x, y are horizontal offsets from the pad centre (x = East, y = North); z is
height above the pad (z = 0 is touchdown). This is not a full 6-DOF quadrotor
with rotor speeds and attitude — it captures what a precision-landing guidance /
flight-test engineer cares about: bounded horizontal acceleration (a proxy for
the tilt limit, |a_h| <= g*tan(tilt_max)), bounded vertical thrust, light aero
drag, and a first-order acceleration-tracking lag so commands are not achieved
instantaneously.

Reduced-order on purpose, and stated as such: the touchdown dispersion,
sink-rate control and vision-in-the-loop behaviour are the objects of study,
not rotor aerodynamics.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

G = 9.80665  # m/s^2


@dataclass(frozen=True)
class Multirotor:
    """Static parameters for a small VTOL (DJI-M300-class quad)."""

    name: str = "quad-2kg"
    mass: float = 2.0                 # kg (documentation only)
    tilt_max: float = np.radians(30)  # bank/tilt limit -> horizontal accel cap
    az_up_max: float = 4.0            # max upward accel (climb/go-around) [m/s^2]
    az_down_max: float = 3.0          # max downward accel (descent) [m/s^2]
    tau_a: float = 0.20               # accel-tracking lag [s]
    k_drag: float = 0.08              # linear aero drag [1/s]

    @property
    def a_h_max(self) -> float:
        """Horizontal acceleration limit from the tilt cap: g*tan(tilt_max)."""
        return G * np.tan(self.tilt_max)


@dataclass
class VehicleState:
    x: float = 0.0
    y: float = 0.0
    z: float = 40.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    # Achieved acceleration (lags the command through tau_a).
    ax: float = 0.0
    ay: float = 0.0
    az: float = 0.0

    def copy(self) -> "VehicleState":
        return replace(self)

    @property
    def pos(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z])

    @property
    def vel(self) -> np.ndarray:
        return np.array([self.vx, self.vy, self.vz])

    @property
    def lateral_offset(self) -> float:
        return float(np.hypot(self.x, self.y))


@dataclass
class AccelCommand:
    ax: float = 0.0
    ay: float = 0.0
    az: float = 0.0


def _saturate_command(cmd: AccelCommand, mr: Multirotor) -> np.ndarray:
    """Clamp the commanded acceleration to the tilt / thrust envelope."""
    a_h = np.array([cmd.ax, cmd.ay])
    h_norm = np.linalg.norm(a_h)
    if h_norm > mr.a_h_max:
        a_h = a_h * (mr.a_h_max / h_norm)
    az = float(np.clip(cmd.az, -mr.az_down_max, mr.az_up_max))
    return np.array([a_h[0], a_h[1], az])


def derivatives(state: VehicleState, cmd: AccelCommand, mr: Multirotor,
                disturb: np.ndarray | None = None) -> np.ndarray:
    """d/dt [x,y,z,vx,vy,vz,ax,ay,az].

    `disturb` is an external acceleration [m/s^2] the controller does not know
    about (wind / gusts), added straight to the velocity derivative.
    """
    a_cmd = _saturate_command(cmd, mr)
    d = np.zeros(3) if disturb is None else np.asarray(disturb, dtype=float)
    # Achieved acceleration tracks the (saturated) command with a first-order lag.
    ax_dot = (a_cmd[0] - state.ax) / mr.tau_a
    ay_dot = (a_cmd[1] - state.ay) / mr.tau_a
    az_dot = (a_cmd[2] - state.az) / mr.tau_a
    # Translational: velocity integrates achieved accel + disturbance - drag.
    vx_dot = state.ax + d[0] - mr.k_drag * state.vx
    vy_dot = state.ay + d[1] - mr.k_drag * state.vy
    vz_dot = state.az + d[2] - mr.k_drag * state.vz
    return np.array([state.vx, state.vy, state.vz,
                     vx_dot, vy_dot, vz_dot,
                     ax_dot, ay_dot, az_dot], dtype=float)


def step_rk4(state: VehicleState, cmd: AccelCommand, dt: float,
             mr: Multirotor, disturb: np.ndarray | None = None) -> VehicleState:
    def f(s: VehicleState) -> np.ndarray:
        return derivatives(s, cmd, mr, disturb)

    def add(s: VehicleState, d: np.ndarray, k: float) -> VehicleState:
        return VehicleState(
            x=s.x + k * d[0], y=s.y + k * d[1], z=s.z + k * d[2],
            vx=s.vx + k * d[3], vy=s.vy + k * d[4], vz=s.vz + k * d[5],
            ax=s.ax + k * d[6], ay=s.ay + k * d[7], az=s.az + k * d[8],
        )

    k1 = f(state)
    k2 = f(add(state, k1, dt / 2))
    k3 = f(add(state, k2, dt / 2))
    k4 = f(add(state, k3, dt))
    incr = (k1 + 2 * k2 + 2 * k3 + k4) / 6.0
    return add(state, incr, dt)
