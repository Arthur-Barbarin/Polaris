"""End-to-end test: pytest -> SCPI client -> SCPI server -> C++ cell.

This is the test that proves the "virtual instrument" abstraction works -
the test code never touches the Cell object directly.
"""
from __future__ import annotations

import pytest


def test_scpi_idn(scpi):
    assert "Polaris" in scpi.query("*IDN?")


def test_scpi_cc_discharge(scpi):
    # 0.5C discharge for 300 simulated seconds.
    # Tick once to settle the bench before sampling the baseline.
    scpi.set_current(1.6)
    scpi.tick(1)
    v_start = scpi.measure_voltage()
    scpi.tick(300)
    v_end = scpi.measure_voltage()
    assert v_end < v_start, "voltage must drop after sustained discharge"
    scpi.write("SOUR:OUTP OFF")


def test_scpi_state_query(scpi):
    state = scpi.query("CELL:STATE?")
    parts = [float(x) for x in state.split(",")]
    assert len(parts) == 8
    soc, v1, v2, T, cyc, t, q, r0 = parts
    assert 0.0 <= soc <= 1.0
    assert q > 0.0
    assert r0 > 0.0


def test_scpi_thermal_chamber_changes_voltage(scpi):
    scpi.write("CELL:RESET 0.5 298.15")
    scpi.set_current(3.2)
    scpi.tick(5)
    v_warm = scpi.measure_voltage()
    scpi.write("CHAM:TEMP 263.15")        # plunge to -10 C
    scpi.set_current(3.2)
    scpi.tick(5)
    v_cold = scpi.measure_voltage()
    assert v_cold < v_warm
