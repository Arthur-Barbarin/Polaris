import math

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daa.geometry import (
    State,
    propagate,
    horizontal_range,
    horizontal_closure_rate,
    time_to_cpa,
    horizontal_miss_distance,
    modified_tau,
    closest_point_of_approach,
)


def test_propagate_constant_velocity():
    s = State(0, 0, 100, 10, 0, -2)
    s2 = propagate(s, 5)
    assert s2.x == 50 and s2.z == 90
    assert (s2.vx, s2.vy, s2.vz) == (10, 0, -2)


def test_heading_and_ground_speed():
    # velocity due East -> heading +pi/2, ground speed = magnitude
    s = State(0, 0, 0, 30, 0, 0)
    assert math.isclose(s.heading, math.pi / 2)
    assert math.isclose(s.ground_speed, 30)


def test_head_on_cpa_is_zero_miss():
    own = State(0, 0, 0, 0, 50, 0)
    intr = State(0, 4000, 0, 0, -50, 0)  # directly ahead, closing
    t = time_to_cpa(own, intr)
    assert math.isclose(t, 40.0, rel_tol=1e-6)      # 4000 m / 100 m/s
    assert horizontal_miss_distance(own, intr) < 1e-6
    assert horizontal_closure_rate(own, intr) < 0   # closing


def test_offset_miss_distance():
    # intruder passes 300 m to the side
    own = State(0, 0, 0, 0, 50, 0)
    intr = State(300, 4000, 0, 0, -50, 0)
    assert math.isclose(horizontal_miss_distance(own, intr), 300.0, rel_tol=1e-6)


def test_modified_tau_infinite_when_diverging():
    own = State(0, 0, 0, 0, 50, 0)
    intr = State(0, 100, 0, 0, 60, 0)  # ahead and pulling away
    assert modified_tau(own, intr, dmod=1219.2) == math.inf


def test_diverging_time_to_cpa_clamped_to_zero():
    own = State(0, 0, 0, 0, 50, 0)
    intr = State(0, 100, 0, 0, 60, 0)
    assert time_to_cpa(own, intr) == 0.0


def test_cpa_sampler_matches_analytic_horizontal():
    own = State(0, 0, 0, 0, 50, 0)
    intr = State(300, 4000, 50, 0, -50, 0)
    t, h, v = closest_point_of_approach(own, intr, horizon=120, dt=0.1)
    assert math.isclose(h, 300.0, abs_tol=1.0)
    assert math.isclose(v, 50.0, abs_tol=1e-6)   # co-level rates -> constant dz
