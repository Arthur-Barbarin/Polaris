"""Closed-loop flight simulator: truth dynamics + sensors + EKF + autopilot.

Runs one scenario end-to-end and returns a FlightLog (the synthetic
telemetry). The loop each tick is:

    truth ground velocity  ->  sensor sample  ->  EKF predict+update
      ->  autopilot.command(EKF estimate)  ->  vehicle.step(control)

The autopilot NEVER sees the true state — only the EKF estimate and the raw
(low-pass-filtered) airspeed reading — so sensor and estimator faults
propagate into closed-loop behaviour exactly as they would on a real aircraft.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np

from .controller import Autopilot, Gains
from .estimator import NavEKF
from .faults import Scenario
from .mission import Mission, along_track_fraction, cross_track_error, default_mission
from .signals import SensorSuite
from .vehicle import Airframe, VehicleState, Wind, step_rk4


@dataclass
class FlightLog:
    scenario: str
    label: str
    dt: float
    t: np.ndarray
    pn: np.ndarray
    pe: np.ndarray
    h: np.ndarray
    Va: np.ndarray
    phi: np.ndarray
    phi_c: np.ndarray
    throttle: np.ndarray
    e_xt: np.ndarray          # true cross-track error on active leg [m]
    h_cmd: np.ndarray         # active-leg altitude command [m]
    est_pos_err: np.ndarray   # EKF horizontal error vs truth [m]
    gps_valid: np.ndarray     # bool
    leg_idx: np.ndarray
    mission_complete: bool
    disturbance_t: float | None
    airframe: Airframe

    def as_dict_of_lists(self) -> dict:
        return {
            "t": self.t.tolist(), "pn": self.pn.tolist(), "pe": self.pe.tolist(),
            "h": self.h.tolist(), "Va": self.Va.tolist(), "phi": self.phi.tolist(),
            "phi_c": self.phi_c.tolist(), "throttle": self.throttle.tolist(),
            "e_xt": self.e_xt.tolist(), "h_cmd": self.h_cmd.tolist(),
            "est_pos_err": self.est_pos_err.tolist(),
            "gps_valid": [bool(x) for x in self.gps_valid.tolist()],
            "leg_idx": self.leg_idx.tolist(),
        }


def simulate(
    scenario: Scenario,
    mission: Mission | None = None,
    airframe: Airframe | None = None,
    dt: float = 0.02,
    t_max: float = 400.0,
    seed: int = 0,
    backend: str = "python",
) -> FlightLog:
    """Run one closed-loop scenario.

    backend="python" uses the pure-Python inner loop; backend="native" runs the
    dynamics step + autopilot in C++ (libpolaris_ft) via ctypes. The two
    produce identical trajectories (see tests/test_native_parity.py).
    """
    mission = mission or default_mission()
    airframe = airframe or Airframe()
    rng = np.random.default_rng(seed)

    use_native = backend == "native"
    if use_native:
        from .native import NativeAutopilot, native_available, step_native
        if not native_available():
            raise RuntimeError(
                "native backend requested but libpolaris_ft is not built "
                "(run `cd cpp && make`)."
            )

    wp0 = mission.waypoints[0]
    state = VehicleState(pn=wp0.n, pe=wp0.e, h=wp0.h,
                         Va=airframe.Va_cruise, psi=0.0, gamma=0.0, phi=0.0)

    if use_native:
        autopilot = NativeAutopilot(mission=mission, airframe=airframe,
                                    gains=Gains(), Va_cmd=airframe.Va_cruise)
    else:
        autopilot = Autopilot(mission=mission, airframe=airframe, gains=Gains(),
                              Va_cmd=airframe.Va_cruise)
    sensors = SensorSuite(scenario.sensor, rng)

    x0 = np.array([wp0.n, wp0.e, airframe.Va_cruise, 0.0, wp0.h])
    ekf = NavEKF(scenario.sensor, x0)

    va_est = airframe.Va_cruise  # low-pass of raw airspeed reading
    va_lp_alpha = 0.1

    logs: list[list[float]] = []
    n_steps = int(t_max / dt)
    completed = False

    for k in range(n_steps):
        t = k * dt

        # --- GPS dropout window ---
        if scenario.gps_dropout is not None:
            t0, t1 = scenario.gps_dropout
            sensors.gps_available = not (t0 <= t <= t1)
        else:
            sensors.gps_available = True

        # --- True ground velocity for sensor synthesis ---
        wn, we = scenario.wind.sample(t)
        cg = np.cos(state.gamma)
        vg_n = state.Va * np.cos(state.psi) * cg + wn
        vg_e = state.Va * np.sin(state.psi) * cg + we

        m = sensors.sample(t, state.pn, state.pe, state.h, vg_n, vg_e, state.Va, state.psi)

        # --- EKF ---
        ekf.predict(dt)
        ekf.update(m)
        est = ekf.state()

        # --- Airspeed estimate the autopilot uses (raw, biased if faulty) ---
        va_est = (1 - va_lp_alpha) * va_est + va_lp_alpha * m.airspeed

        # --- Autopilot closes on the ESTIMATE ---
        ctrl = autopilot.command(est.pn, est.pe, est.h, va_est, est.course, dt)

        # --- True cross-track on the active leg ---
        wp_from, wp_to = mission.leg(autopilot.leg_idx)
        e_xt = cross_track_error(state.pn, state.pe, wp_from, wp_to)
        pos_err = float(np.hypot(est.pn - state.pn, est.pe - state.pe))

        logs.append([
            t, state.pn, state.pe, state.h, state.Va, state.phi,
            ctrl.phi_c, ctrl.throttle, e_xt, wp_to.h, pos_err,
            float(m.gps_valid), float(autopilot.leg_idx),
        ])

        # --- Advance truth ---
        if use_native:
            state = step_native(state, ctrl, scenario.wind, t, dt, airframe, scenario.actuator)
        else:
            state = step_rk4(state, ctrl, scenario.wind, t, dt, airframe, scenario.actuator)

        # --- Mission-complete check on the final leg ---
        last_from, last_to = mission.leg(mission.n_legs - 1)
        if autopilot.leg_idx == mission.n_legs - 1:
            if along_track_fraction(state.pn, state.pe, last_from, last_to) >= 0.98:
                completed = True
                break

    arr = np.array(logs, dtype=float)
    return FlightLog(
        scenario=scenario.name, label=scenario.label, dt=dt,
        t=arr[:, 0], pn=arr[:, 1], pe=arr[:, 2], h=arr[:, 3], Va=arr[:, 4],
        phi=arr[:, 5], phi_c=arr[:, 6], throttle=arr[:, 7], e_xt=arr[:, 8],
        h_cmd=arr[:, 9], est_pos_err=arr[:, 10],
        gps_valid=arr[:, 11].astype(bool), leg_idx=arr[:, 12].astype(int),
        mission_complete=completed, disturbance_t=scenario.disturbance_t,
        airframe=airframe,
    )
