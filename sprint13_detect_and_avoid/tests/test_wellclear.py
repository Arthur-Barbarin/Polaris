import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daa.geometry import State
from daa.wellclear import (
    DWC,
    NMAC,
    FT,
    loss_of_well_clear,
    predicted_lowc,
    is_nmac,
    separation_at_cpa,
)


def test_thresholds_match_do365():
    # DO-365 values, declared from feet.
    assert math.isclose(DWC.dmod, 4000 * FT)
    assert math.isclose(DWC.hmd_thr, 4000 * FT)
    assert DWC.taumod_thr == 35.0
    assert math.isclose(DWC.zthr, 450 * FT)
    assert math.isclose(NMAC.horizontal, 500 * FT)
    assert math.isclose(NMAC.vertical, 100 * FT)


def test_well_separated_pair_is_clear():
    own = State(0, 0, 0, 0, 50, 0)
    intr = State(10000, 0, 0, 0, 50, 0)  # 10 km abeam, parallel
    assert not loss_of_well_clear(own, intr)


def test_co_located_pair_is_lowc():
    own = State(0, 0, 0, 0, 50, 0)
    intr = State(100, 0, 10, 0, -50, 0)  # 100 m away, co-altitude, closing
    assert loss_of_well_clear(own, intr)


def test_vertical_separation_defeats_lowc():
    # horizontally converging but 300 m apart vertically (> ZTHR 137 m)
    own = State(0, 0, 0, 0, 50, 0)
    intr = State(50, 300, 300, 0, -50, 0)
    assert not loss_of_well_clear(own, intr)


def test_predicted_lowc_sees_future_conflict():
    own = State(0, 0, 0, 0, 50, 0)
    intr = State(0, 5000, 0, 0, -50, 0)  # head-on, still 5 km out
    assert not loss_of_well_clear(own, intr)          # clear right now
    will, t = predicted_lowc(own, intr, lookahead=60)
    assert will and 0 < t < 60                         # but predicted soon


def test_head_on_is_nmac_but_offset_is_not():
    own = State(0, 0, 0, 0, 50, 0)
    head_on = State(0, 5000, 0, 0, -50, 0)
    offset = State(400, 5000, 0, 0, -50, 0)  # passes 400 m abeam
    assert is_nmac(own, head_on, horizon=120)
    assert not is_nmac(own, offset, horizon=120)


def test_every_nmac_is_a_future_lowc():
    # the NMAC volume is strictly inside the Well Clear volume
    own = State(0, 0, 0, 0, 50, 0)
    intr = State(0, 4000, 0, 0, -50, 0)
    assert is_nmac(own, intr, horizon=120)
    will, _ = predicted_lowc(own, intr, lookahead=120)
    assert will
