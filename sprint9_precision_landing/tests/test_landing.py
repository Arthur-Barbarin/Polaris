"""pytest suite for the precision-landing studio (fast: dt=0.02, few seeds)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from polaris_pl import (
    ALL_SCENARIOS, AccelCommand, Camera, CameraConfig, LandingPad, LandingTriage,
    Multirotor, VehicleState, cep, compute_metrics, grade, simulate, step_rk4,
)
from polaris_pl.faults import (
    crosswind, gps_bias, gust, low_light, nominal, offset_pad, vision_dropout,
)


# --------------------------------------------------------------------- dynamics
def test_horizontal_accel_saturates_at_tilt_limit():
    mr = Multirotor()
    s = VehicleState(x=0, y=0, z=20)
    # Command a huge horizontal accel; achieved should approach the tilt cap.
    for _ in range(200):
        s = step_rk4(s, AccelCommand(ax=100.0, ay=0.0, az=0.0), 0.02, mr)
    assert abs(s.ax) <= mr.a_h_max + 1e-6
    assert s.ax > 0.8 * mr.a_h_max


def test_descends_under_commanded_sink():
    mr = Multirotor()
    s = VehicleState(z=20)
    for _ in range(200):
        s = step_rk4(s, AccelCommand(az=-1.0), 0.02, mr)
    assert s.z < 20.0 and s.vz < 0


# ----------------------------------------------------------------------- camera
def test_camera_fov_gating():
    cam = Camera(CameraConfig(), LandingPad(), np.random.default_rng(0))
    # Pad far to the side at low altitude -> outside FOV -> not valid.
    m = cam.sample(0.0, VehicleState(x=50.0, y=0.0, z=2.0))
    assert m is not None and not m.valid


def test_vision_noise_scales_with_altitude_with_floor():
    cfg = CameraConfig()
    hi = Camera(cfg, LandingPad(), np.random.default_rng(0)).sample(
        0.0, VehicleState(z=30)).sigma_world
    lo = Camera(cfg, LandingPad(), np.random.default_rng(0)).sample(
        0.0, VehicleState(z=2)).sigma_world
    assert hi > lo
    assert lo >= cfg.sigma_floor_m - 1e-9    # never below the floor


# --------------------------------------------------------- estimator / handover
def test_handover_corrects_pad_offset():
    m = compute_metrics(simulate(offset_pad(), seed=1, dt=0.02))
    assert m.landed and m.touchdown_lateral < 0.5   # vision beats a 2.2 m offset


def test_handover_corrects_gps_bias():
    m = compute_metrics(simulate(gps_bias(), seed=1, dt=0.02))
    assert m.landed and m.touchdown_lateral < 0.5


def test_disagreement_reveals_hidden_faults():
    dn = compute_metrics(simulate(nominal(), seed=1, dt=0.02)).gps_vision_disagree
    do = compute_metrics(simulate(offset_pad(), seed=1, dt=0.02)).gps_vision_disagree
    dg = compute_metrics(simulate(gps_bias(), seed=1, dt=0.02)).gps_vision_disagree
    assert dg > do > dn      # bigger fault -> bigger GPS/vision disagreement


# ------------------------------------------------------------ guidance outcomes
def test_nominal_lands_and_passes():
    r = grade(compute_metrics(simulate(nominal(), seed=0, dt=0.02)))
    assert r.outcome == "PASS"


def test_vision_dropout_triggers_go_around():
    log = simulate(vision_dropout(), seed=0, dt=0.02)
    assert log.outcome == "GO_AROUND"
    assert log.z[-1] > 12.0    # climbed clear


def test_late_gust_triggers_go_around():
    assert simulate(gust(), seed=0, dt=0.02).outcome == "GO_AROUND"


def test_low_light_lands_but_fails_vision_card():
    r = grade(compute_metrics(simulate(low_light(), seed=0, dt=0.02)))
    assert r.outcome == "FAIL"
    failed = {c.name for c in r.results if not c.passed}
    assert "Vision availability on final" in failed


# ---------------------------------------------------------------- dispersion
def test_nominal_cep_is_tight():
    pts = []
    for s in range(20):
        log = simulate(nominal(), seed=s, dt=0.02)
        if log.outcome == "LANDED":
            pts.append([log.touchdown_x, log.touchdown_y])
    c = cep(np.array(pts))
    assert c.n >= 18
    assert c.cep50 < 0.2


def test_never_lands_without_vision():
    """Safety guard: with vision fully unavailable the guidance must go around,
    never blind-land — so a cm-class CEP can never come from GPS alone."""
    from polaris_pl import Scenario
    from polaris_pl.camera import CameraConfig
    for seed in range(6):
        log = simulate(Scenario("blind", "BLIND", camera=CameraConfig(p_detect=0.0)),
                       seed=seed, dt=0.02)
        assert log.outcome != "LANDED"


def test_touchdown_error_grows_with_wind():
    """Sanity: stronger steady wind -> larger touchdown error (until go-around)."""
    from polaris_pl import Scenario
    e0 = compute_metrics(simulate(Scenario("w0", "W", wind=(0.0, 0.0)), seed=0, dt=0.02))
    e2 = compute_metrics(simulate(Scenario("w2", "W", wind=(2.0, 0.0)), seed=0, dt=0.02))
    assert e0.landed and e2.landed
    assert e2.touchdown_lateral > e0.touchdown_lateral


# ------------------------------------------------- post-audit regression guards
def test_cep_reports_accuracy_not_just_precision():
    """CEP about the pad must expose the steady-wind touchdown bias that CEP
    about the sample mean hides."""
    from polaris_pl import Scenario
    pts = []
    for s in range(30):
        log = simulate(Scenario("cw", "CW", wind=(1.6, -1.0)), seed=s, dt=0.02)
        if log.outcome == "LANDED":
            pts.append([log.touchdown_x, log.touchdown_y])
    c = cep(np.array(pts))
    assert c.bias > 0.02                       # a real standing offset exists
    assert c.cep50_pad > 1.3 * c.cep50         # accuracy is worse than precision


def test_touchdown_radius_drives_the_card():
    """The pad's acceptance radius is load-bearing, not decorative."""
    from polaris_pl import Scenario
    from polaris_pl.pad import LandingPad
    base = compute_metrics(simulate(Scenario("n", "N"), seed=0, dt=0.02))
    td = base.touchdown_lateral
    tight = grade(compute_metrics(simulate(
        Scenario("n", "N", pad=LandingPad(touchdown_radius_m=td * 0.5)), seed=0, dt=0.02)))
    loose = grade(compute_metrics(simulate(
        Scenario("n", "N", pad=LandingPad(touchdown_radius_m=td * 2.0)), seed=0, dt=0.02)))
    assert tight.outcome == "FAIL" and loose.outcome == "PASS"


def test_airframe_is_injectable_and_matters():
    """simulate() must accept an airframe, and it must change behaviour."""
    from polaris_pl import Multirotor, Scenario
    sluggish = Multirotor(tilt_max=np.radians(12), tau_a=0.6)
    d = compute_metrics(simulate(Scenario("w", "W", wind=(1.5, 0.0)), seed=0,
                                 dt=0.02, vehicle=sluggish))
    n = compute_metrics(simulate(Scenario("w", "W", wind=(1.5, 0.0)), seed=0, dt=0.02))
    assert d.max_lateral_final > n.max_lateral_final    # sluggish tracks worse


def test_narrow_fov_reduces_high_altitude_vision():
    """The camera FOV limit must actually gate, not be inert."""
    from polaris_pl.faults import narrow_fov, nominal
    nf = compute_metrics(simulate(narrow_fov(), seed=0, dt=0.02))
    nom = compute_metrics(simulate(nominal(), seed=0, dt=0.02))
    assert nf.vision_avail_high < nom.vision_avail_high - 0.05


def test_triage_separates_modes():
    mets = []
    for fn in ALL_SCENARIOS.values():
        for seed in range(8):
            mets.append(compute_metrics(simulate(fn(), seed=seed, dt=0.02)))
    tri = LandingTriage(n_components=6, n_clusters=18).fit(mets)
    assert LandingTriage.accuracy(tri.predict(mets)) > 0.8
