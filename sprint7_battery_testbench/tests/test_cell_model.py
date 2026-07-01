"""Unit-level checks on the C++ cell behaviour."""
from __future__ import annotations

import math

import pytest

from polaris_bms import Cell, Fault, ocv_of_soc


def test_ocv_monotonic_in_soc():
    socs = [i / 20 for i in range(21)]
    vs = [ocv_of_soc(s) for s in socs]
    assert vs == sorted(vs), "OCV(SOC) must be monotonic non-decreasing"
    assert vs[0] == pytest.approx(2.75, abs=1e-6)
    assert vs[-1] == pytest.approx(4.20, abs=1e-6)


def test_zero_current_holds_soc():
    c = Cell(soc0=0.5)
    s0 = c.snapshot().soc
    for _ in range(1000):
        c.step(0.0, 1.0)
    assert c.snapshot().soc == pytest.approx(s0, abs=1e-9)


def test_coulomb_conservation_at_1c():
    """At 1C discharge for 3600s the cell should drop exactly one capacity unit."""
    c = Cell(soc0=1.0)
    cap = c.snapshot().q_now_ah
    i = cap  # 1C
    for _ in range(3600):
        c.step(i, 1.0)
    # Account for capacity fade over the 1h discharge.
    expected_drop = 1.0  # one full capacity
    assert c.snapshot().soc == pytest.approx(1.0 - expected_drop, abs=0.02)


def test_voltage_drops_with_higher_c_rate():
    a = Cell(soc0=0.8)
    b = Cell(soc0=0.8)
    v_low  = a.step(1.0, 1.0)
    v_high = b.step(5.0, 1.0)
    assert v_high < v_low - 0.05, "5C must show clearly larger IR drop than 1C"


def test_relaxation_returns_toward_ocv():
    c = Cell(soc0=0.5)
    c.step(3.0, 60.0)         # 1 minute discharge
    v_loaded = c.terminal_voltage(3.0)
    for _ in range(600):       # 10 minute rest
        c.step(0.0, 1.0)
    v_rested = c.terminal_voltage(0.0)
    ocv = ocv_of_soc(c.snapshot().soc)
    assert abs(v_rested - ocv) < abs(v_loaded - ocv)


def test_temperature_increases_resistance():
    cold = Cell(soc0=0.5, temperature_k=263.15)   # -10 C
    warm = Cell(soc0=0.5, temperature_k=313.15)   # +40 C
    v_cold = cold.step(3.2, 1.0)
    v_warm = warm.step(3.2, 1.0)
    assert v_cold < v_warm, "cold cell should sag more under load"


@pytest.mark.parametrize("fault", [Fault.INTERNAL_SHORT, Fault.SEI_GROWTH])
def test_fault_injection_changes_behaviour(fault):
    healthy = Cell(soc0=0.5)
    faulty  = Cell(soc0=0.5)
    faulty.set_fault(fault, 0.8)
    vh = [healthy.step(3.2, 1.0) for _ in range(60)]
    vf = [faulty.step(3.2, 1.0) for _ in range(60)]
    assert abs(vh[-1] - vf[-1]) > 1e-3, "fault should leave a measurable signature"
