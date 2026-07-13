"""Closed-loop precision-landing simulator.

Each tick: IMU -> KF.predict; GPS / rangefinder / vision -> KF.update;
guidance.command(estimate) -> vehicle.step(with wind). The guidance never sees
truth. Produces an ApproachLog: the synthetic approach telemetry plus the
landing outcome and touchdown metrics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np

from .camera import Camera
from .estimator import LandingKF
from .faults import Scenario
from .guidance import LandingGuidance, Phase
from .signals import SensorSuite
from .vehicle import AccelCommand, Multirotor, VehicleState, step_rk4

FINAL_APPROACH_Z = 10.0  # height below which we score vision availability [m]


@dataclass
class ApproachLog:
    scenario: str
    label: str
    dt: float
    t: np.ndarray
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    est_x: np.ndarray
    est_y: np.ndarray
    est_z: np.ndarray
    sink: np.ndarray            # true sink rate (-vz) [m/s]
    lateral_true: np.ndarray    # true offset from actual pad [m]
    lateral_est: np.ndarray     # estimated lateral offset [m]
    phase: List[str]
    vision_valid: np.ndarray    # per-frame vision detection (bool)
    # Outcome
    outcome: str                # LANDED | GO_AROUND | TIMEOUT
    go_around_reason: str
    touchdown_x: float          # relative to actual pad [m]
    touchdown_y: float
    touchdown_lateral: float
    touchdown_sink: float
    vision_avail_final: float   # fraction of final-approach frames detected
    vision_avail_high: float    # fraction detected above the final-approach ht
    gps_vision_disagree: float  # mean |GPS - vision| horizontal offset [m]
    pad_xy: tuple
    touchdown_radius: float     # pad acceptance radius [m] (drives the card)


def simulate(scenario: Scenario, seed: int = 0, dt: float = 0.02,
             t_max: float = 40.0, vehicle: Multirotor | None = None) -> ApproachLog:
    rng = np.random.default_rng(seed)
    # Airframe precedence: explicit arg > scenario override > default.
    mr = vehicle or scenario.vehicle or Multirotor()
    pad = scenario.pad

    # Initial geometry with per-run dispersion on the entry offset.
    ox = scenario.init_offset[0] + rng.normal(0, 1.0)
    oy = scenario.init_offset[1] + rng.normal(0, 1.0)
    state = VehicleState(x=ox, y=oy, z=scenario.init_z)

    suite = SensorSuite(scenario.sensor, rng)
    camera = Camera(scenario.camera, pad, rng)
    guidance = LandingGuidance(mr)

    # KF starts from the (biased/noisy) GPS-referenced entry estimate.
    x0 = np.array([ox + rng.normal(0, scenario.sensor.gps_xy_std),
                   oy + rng.normal(0, scenario.sensor.gps_xy_std),
                   scenario.init_z, 0.0, 0.0, 0.0])
    kf = LandingKF(x0)

    rows: list[list] = []
    phases: list[str] = []
    n_final = 0
    n_final_seen = 0
    n_high = 0
    n_high_seen = 0
    disagree_sum = 0.0
    disagree_n = 0
    last_gps = None
    outcome = "TIMEOUT"
    td_x = td_y = td_sink = np.nan

    n_steps = int(t_max / dt)
    for k in range(n_steps):
        t = k * dt

        # --- Camera availability (occlusion window / late acquisition) ---
        avail = True
        if scenario.vision_block_t is not None:
            t0, t1 = scenario.vision_block_t
            if t0 <= t <= t1:
                avail = False
        if scenario.acquire_below_z is not None and state.z > scenario.acquire_below_z:
            avail = False
        camera.available = avail

        # --- Sensors + filter ---
        kf.predict(suite.imu_accel(state), dt)
        gps = suite.gps(t, state)
        if gps is not None:
            kf.update_gps(gps.x, gps.y, scenario.sensor.gps_xy_std)
            last_gps = gps
        kf.update_range(suite.rangefinder(state), scenario.sensor.range_std)

        vis = camera.sample(t, state)
        vis_valid = False
        if vis is not None:
            guidance.note_vision(t, vis.valid)
            vis_valid = vis.valid
            if vis.valid:
                kf.update_vision(vis.rel_x, vis.rel_y, max(vis.sigma_world, 1e-3))
                # GPS (referenced to expected pad) vs vision (referenced to the
                # actual pad): their disagreement reveals a pad offset or a GPS
                # bias even when the handover compensates it end-to-end.
                if last_gps is not None:
                    disagree_sum += float(np.hypot(last_gps.x - vis.rel_x,
                                                   last_gps.y - vis.rel_y))
                    disagree_n += 1
            if state.z <= FINAL_APPROACH_Z:
                n_final += 1
                n_final_seen += int(vis.valid)
            else:
                n_high += 1
                n_high_seen += int(vis.valid)

        est = kf.state()
        cmd, phase = guidance.command(est, t, dt)

        lateral_true = float(np.hypot(state.x - pad.x, state.y - pad.y))
        rows.append([t, state.x, state.y, state.z, est.x[0], est.x[1], est.x[2],
                     -state.vz, lateral_true, est.lateral_offset, float(vis_valid)])
        phases.append(phase.value)

        # --- Advance truth ---
        state = step_rk4(state, cmd, dt, mr, disturb=scenario.wind_at(t))

        # --- Termination ---
        if phase != Phase.GO_AROUND and state.z <= 0.0:
            outcome = "LANDED"
            td_x = state.x - pad.x
            td_y = state.y - pad.y
            td_sink = -state.vz
            break
        if phase == Phase.GO_AROUND and state.z >= max(12.0, 0.4 * scenario.init_z):
            outcome = "GO_AROUND"
            break

    arr = np.array(rows, dtype=float)
    td_lat = float(np.hypot(td_x, td_y)) if outcome == "LANDED" else np.nan
    vis_final = (n_final_seen / n_final) if n_final > 0 else 0.0
    return ApproachLog(
        scenario=scenario.name, label=scenario.label, dt=dt,
        t=arr[:, 0], x=arr[:, 1], y=arr[:, 2], z=arr[:, 3],
        est_x=arr[:, 4], est_y=arr[:, 5], est_z=arr[:, 6],
        sink=arr[:, 7], lateral_true=arr[:, 8], lateral_est=arr[:, 9],
        phase=phases, vision_valid=arr[:, 10].astype(bool),
        outcome=outcome, go_around_reason=guidance.go_around_reason,
        touchdown_x=td_x, touchdown_y=td_y, touchdown_lateral=td_lat,
        touchdown_sink=td_sink, vision_avail_final=vis_final,
        vision_avail_high=((n_high_seen / n_high) if n_high else 0.0),
        gps_vision_disagree=(disagree_sum / disagree_n) if disagree_n else 0.0,
        pad_xy=(pad.x, pad.y), touchdown_radius=pad.touchdown_radius_m,
    )
