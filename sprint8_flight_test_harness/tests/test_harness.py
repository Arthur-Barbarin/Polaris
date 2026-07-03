"""pytest suite for the flight-test harness.

Fast by design (dt=0.1, few seeds) so it runs as a pre-commit-style gate.
Groups: dynamics, controller/guidance, estimator, test cards, triage.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from polaris_ft import (
    ALL_SCENARIOS, Actuator, Airframe, ControlInput, NavEKF, SensorConfig,
    VehicleState, Wind, compute_metrics, grade, simulate, step_rk4,
)
from polaris_ft.faults import (
    aileron_loss, airspeed_bias, gps_dropout, nominal, wind_step,
)
from polaris_ft.triage import FlightTriage
from polaris_ft.vehicle import G


# --------------------------------------------------------------------- dynamics
def test_coordinated_turn_radius():
    af = Airframe()
    V, phi = 30.0, np.radians(30)
    st = VehicleState(Va=V, phi=phi, gamma=0.0)
    nxt = step_rk4(st, ControlInput(phi_c=phi, throttle=0.5), Wind(), 0.0, 0.1, af, Actuator())
    psi_dot = (nxt.psi - st.psi) / 0.1
    R = V / psi_dot
    assert R == pytest.approx(V**2 / (G * np.tan(phi)), rel=0.1)


def test_level_cruise_holds_altitude():
    af = Airframe()
    st = VehicleState(Va=30.0, h=100.0, gamma=0.0)
    for _ in range(50):
        st = step_rk4(st, ControlInput(phi_c=0, gamma_c=0, throttle=0.5), Wind(), 0.0, 0.1, af, Actuator())
    assert st.h == pytest.approx(100.0, abs=1.0)


def test_tailwind_increases_ground_speed():
    af = Airframe()
    st = VehicleState(Va=30.0, psi=0.0, gamma=0.0)
    nxt = step_rk4(st, ControlInput(throttle=0.5), Wind(Wn=6.0), 0.0, 1.0, af, Actuator())
    assert (nxt.pn - st.pn) == pytest.approx(36.0, abs=0.5)


# ------------------------------------------------------------------- controller
def test_mission_completes_nominal():
    log = simulate(nominal(), seed=0, dt=0.1)
    assert log.mission_complete
    assert log.leg_idx[-1] == log.leg_idx.max()


def test_straight_leg_tracking_is_tight():
    m = compute_metrics(simulate(nominal(), seed=0, dt=0.1))
    assert m.cross_track_rms < 8.0     # straight-leg RMS well under bound


# -------------------------------------------------------------------- estimator
def test_ekf_beats_raw_gps():
    m = compute_metrics(simulate(nominal(), seed=1, dt=0.1))
    # Raw per-axis GPS sigma is 2 m; fused estimate should beat a single fix.
    assert m.est_pos_rmse < 2.0 * SensorConfig().gps_pos_std


def test_ekf_bounded_during_gps_dropout():
    m = compute_metrics(simulate(gps_dropout(), seed=1, dt=0.1))
    # Error grows without GPS but must not diverge.
    assert m.est_pos_rmse > compute_metrics(simulate(nominal(), seed=1, dt=0.1)).est_pos_rmse
    assert m.est_pos_max < 150.0
    assert m.mission_complete


# -------------------------------------------------------------------- testcards
def test_nominal_passes():
    assert grade(compute_metrics(simulate(nominal(), seed=0, dt=0.1))).passed


@pytest.mark.parametrize("fn,metric", [
    (wind_step, "cross_track_max"),
    (aileron_loss, "cross_track_rms"),
])
def test_disturbance_fails_expected_card(fn, metric):
    r = grade(compute_metrics(simulate(fn(), seed=0, dt=0.1)))
    assert not r.passed
    failed = {c.metric for c in r.results if not c.passed}
    assert metric in failed


def test_airspeed_bias_shows_in_airspeed_error():
    m = compute_metrics(simulate(airspeed_bias(), seed=0, dt=0.1))
    assert abs(m.airspeed_mean_err) > 2.0


def test_card_report_is_traceable():
    r = grade(compute_metrics(simulate(nominal(), seed=0, dt=0.1)))
    assert r.version  # versioned criteria
    assert all(hasattr(c, "bound") for c in r.results)


# ------------------------------------------------------------------------ triage
def test_triage_separates_fault_families():
    mets = []
    for fn in ALL_SCENARIOS.values():
        for seed in range(4):
            mets.append(compute_metrics(simulate(fn(), seed=seed, dt=0.1)))
    tri = FlightTriage(n_components=4, n_clusters=10).fit(mets)
    acc = FlightTriage.accuracy(tri.predict(mets))
    assert acc > 0.8
