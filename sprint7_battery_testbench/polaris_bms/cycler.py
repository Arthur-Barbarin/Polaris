"""Accelerated cycling harness - generates the data the SoH/RUL and
failure-triage pipelines train and predict on.

A cycle = CC discharge to v_min, rest, CC-CV charge to v_max with current
taper at the end, rest. Per cycle we record summary features that mirror
what a real battery test report contains: discharge capacity, charge time,
mean voltage, dV/dQ peak position, terminal IR drop on the first 1s pulse.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, List, Optional

import numpy as np

from .native import Cell, Fault


@dataclass
class CycleRecord:
    cycle: int
    discharge_capacity_ah: float
    charge_capacity_ah: float
    coulombic_efficiency: float
    mean_discharge_voltage: float
    ir_drop_v: float
    rest_relaxation_v: float
    peak_charge_dvdq: float        # max dV/dQ across the entire charge step
    soh_pct: float
    # Trajectory features (Δ vs previous cycle) - degradation modes have
    # distinct signatures in how features evolve, not just their absolute level.
    d_soh_pct: float = 0.0
    d_ir_drop_v: float = 0.0
    d_mean_voltage_v: float = 0.0
    fault: str = ""


def _run_one_cycle(cell: Cell, *,
                   discharge_a: float = 3.2,
                   charge_a: float = 1.6,
                   v_min: float = 2.85,
                   v_max: float = 4.15,
                   taper_a: float = 0.2,
                   dt: float = 1.0) -> CycleRecord:
    # ---- discharge ----
    v0 = cell.terminal_voltage(0.0)
    v_after_pulse = cell.step(discharge_a, dt)
    ir_drop = v0 - v_after_pulse
    discharge_ah = discharge_a * dt / 3600.0
    voltages = [v_after_pulse]
    t = dt
    while cell.terminal_voltage(0.0) > v_min and t < 8 * 3600:
        v = cell.step(discharge_a, dt)
        discharge_ah += discharge_a * dt / 3600.0
        voltages.append(v)
        t += dt
    mean_v = float(np.mean(voltages))
    # ---- rest ----
    v_loaded = cell.terminal_voltage(0.0)
    for _ in range(int(300 / dt)):
        cell.step(0.0, dt)
    v_rested = cell.terminal_voltage(0.0)
    rest_relax = v_rested - v_loaded
    # ---- CC-CV charge ----
    charge_ah = 0.0
    last_v = cell.terminal_voltage(0.0)
    dvdq_peak = 0.0
    current = -abs(charge_a)
    t = 0.0
    while abs(current) > taper_a and t < 8 * 3600:
        v = cell.step(current, dt)
        d_ah = abs(current) * dt / 3600.0
        charge_ah += d_ah
        if d_ah > 0:
            dvdq = (v - last_v) / d_ah
            dvdq_peak = max(dvdq_peak, dvdq)
        last_v = v
        # CV taper once we hit v_max
        if v >= v_max:
            current *= 0.985
        t += dt
    # ---- rest ----
    for _ in range(int(120 / dt)):
        cell.step(0.0, dt)
    # SoH filled in by the campaign loop (needs the BoL reference).
    return CycleRecord(
        cycle=-1,
        discharge_capacity_ah=discharge_ah,
        charge_capacity_ah=charge_ah,
        coulombic_efficiency=discharge_ah / charge_ah if charge_ah > 0 else 0.0,
        mean_discharge_voltage=mean_v,
        ir_drop_v=ir_drop,
        rest_relaxation_v=rest_relax,
        peak_charge_dvdq=dvdq_peak,
        soh_pct=0.0,
        fault="",
    )


def run_cycling_campaign(
    n_cycles: int = 40,
    fault: Fault = Fault.NONE,
    fault_severity: float = 0.0,
    temperature_k: float = 298.15,
    seed: int = 0,
) -> List[CycleRecord]:
    """Run an accelerated campaign and return per-cycle records."""
    cell = Cell(soc0=1.0, temperature_k=temperature_k)
    if fault != Fault.NONE:
        cell.set_fault(fault, fault_severity)
    # Capture the BoL capacity reference for the SoH metric.
    bol_q = cell.snapshot().q_now_ah
    records: List[CycleRecord] = []
    for k in range(n_cycles):
        rec = _run_one_cycle(cell)
        rec.cycle = k + 1
        rec.soh_pct = 100.0 * cell.snapshot().q_now_ah / bol_q
        rec.fault = fault.name
        if records:
            prev = records[-1]
            rec.d_soh_pct        = rec.soh_pct - prev.soh_pct
            rec.d_ir_drop_v      = rec.ir_drop_v - prev.ir_drop_v
            rec.d_mean_voltage_v = rec.mean_discharge_voltage - prev.mean_discharge_voltage
        records.append(rec)
    return records
