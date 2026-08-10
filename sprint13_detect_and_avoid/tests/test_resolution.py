import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daa.geometry import State, horizontal_miss_distance
from daa.resolution import (
    Maneuver,
    MANEUVER_SET,
    ResolutionParams,
    select_ra,
    apply_maneuver,
)


def test_maneuver_set_is_closed_and_named():
    names = {m.name for m in MANEUVER_SET}
    assert names == {"MAINTAIN", "CLIMB", "DESCEND", "TURN_RIGHT", "TURN_LEFT"}


def test_apply_maneuver_preserves_ground_speed_on_turn():
    s = State(0, 0, 0, 0, 50, 0)
    m = Maneuver("TURN_RIGHT", turn_rate=math.radians(3))
    s2 = apply_maneuver(s, m, dt=1.0)
    assert math.isclose(s2.ground_speed, 50.0, rel_tol=1e-9)
    assert s2.vx > 0  # turned toward East (clockwise/right)


def test_apply_maneuver_climb_sets_vertical_rate():
    s = State(0, 0, 0, 0, 50, 0)
    m = Maneuver("CLIMB", vertical_rate=2.54, sets_vertical=True)
    s2 = apply_maneuver(s, m, dt=1.0)
    assert math.isclose(s2.vz, 2.54)
    assert math.isclose(s2.z, 2.54)


def test_ra_increases_miss_distance_on_head_on():
    own = State(0, 0, 0, 0, 50, 0)
    intr = State(0, 4000, 0, 0, -50, 0)  # head-on, ~0 miss distance
    assert horizontal_miss_distance(own, intr) < 1.0
    ra, pred_min = select_ra(own, intr)
    assert ra.name != "MAINTAIN"          # must do something
    assert pred_min > 200.0               # and it must open real separation


def test_ra_is_deterministic():
    own = State(0, 0, 0, 0, 50, 0)
    intr = State(200, 4000, 0, 0, -50, 0)
    a, _ = select_ra(own, intr)
    b, _ = select_ra(own, intr)
    assert a.name == b.name


def test_no_conflict_prefers_maintain():
    # already diverging: no candidate beats simply holding course
    own = State(0, 0, 0, 0, 50, 0)
    intr = State(8000, 0, 0, 0, 50, 0)  # 8 km abeam, parallel
    ra, _ = select_ra(own, intr)
    assert ra.name == "MAINTAIN"
