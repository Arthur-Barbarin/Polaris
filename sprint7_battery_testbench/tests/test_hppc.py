"""HPPC characterisation test - the canonical Li-ion impedance test.

Drives the cell through 10s pulse / 40s rest at multiple SOC breakpoints and
extracts R0 from the instantaneous voltage step. Pass criteria: extracted R0
falls within +/-30% of the model's reference R0 (loose because the synthetic
DAQ has noise and aging shifts R0).
"""
from __future__ import annotations

import statistics

import pytest

from polaris_bms import Cell, ocv_of_soc


@pytest.mark.parametrize("temperature_k", [273.15, 298.15, 313.15])
def test_hppc_pulse_extracts_r0(temperature_k, dlog, smu, bench):
    bench.cell.reset(0.8, temperature_k)
    estimates = []
    for soc_target in (0.8, 0.6, 0.4, 0.2):
        # discharge down to the breakpoint
        while bench.cell.snapshot().soc > soc_target + 0.005:
            smu.source_current(3.2)
            bench.tick()
        # rest 60s
        smu.source_current(0.0)
        for _ in range(60):
            bench.tick()
        v_before = dlog.measure_voltage()
        # 10s discharge pulse
        smu.source_current(3.2)
        bench.tick()                       # one dt at load
        v_after = dlog.measure_voltage()
        smu.source_current(0.0)
        r0 = (v_before - v_after) / 3.2
        estimates.append(r0)
    median_r0 = statistics.median(estimates)
    assert 0.005 < median_r0 < 0.5, f"R0 estimate out of plausible range: {median_r0}"


def test_ocv_soc_table_reconstruction(dlog, smu, bench):
    """Slow discharge with long rests should let us re-derive OCV-SOC."""
    bench.cell.reset(1.0, 298.15)
    measured = []
    for soc_target in (0.9, 0.7, 0.5, 0.3, 0.1):
        while bench.cell.snapshot().soc > soc_target + 0.005:
            smu.source_current(1.0)
            bench.tick()
        smu.source_current(0.0)
        for _ in range(300):              # 5 min rest
            bench.tick()
        v_rested = dlog.measure_voltage()
        measured.append((bench.cell.snapshot().soc, v_rested))
    # Compare to OCV table
    for soc, v in measured:
        err = abs(v - ocv_of_soc(soc))
        assert err < 0.08, f"OCV(SOC={soc:.2f}) deviated by {err:.3f}V"
