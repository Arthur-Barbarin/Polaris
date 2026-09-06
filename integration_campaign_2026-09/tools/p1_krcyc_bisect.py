"""Phase 1, residual of F1-1: after restoring k_cyc = 0.0030 the SoH trace
reproduces the shipped dataset exactly, but the impedance-derived features
(ir_drop_v, peak_charge_dvdq) are still ~3-7 % off. Bisect the resistance-growth
coefficient k_r_cyc the same way. Pure-Python backend, nothing written.
"""
import json, sys, statistics as st
from pathlib import Path

S7 = Path(__file__).resolve().parents[2] / "sprint7_battery_testbench"
sys.path.insert(0, str(S7))
import platform; platform.system = lambda: "Darwin"
from polaris_bms import native as n
assert not n.native_available()
from polaris_bms.cycler import run_cycling_campaign
from polaris_bms import Fault

sh = json.load(open("/tmp/shipped_cycle_records.json"))
def mean_of(recs, k, attr=False):
    return st.mean((getattr(r, k) if attr else r[k]) for r in recs
                   if (r.cycle if attr else r["cycle"]) > 1)
tgt = {lab: {k: mean_of([r for r in sh if r["fault"] == lab], k)
             for k in ("ir_drop_v", "peak_charge_dvdq")}
       for lab in ("HEALTHY", "LITHIUM_PLATING")}

SCEN = {"HEALTHY": (Fault.NONE, 0.0, 298.15),
        "LITHIUM_PLATING": (Fault.LITHIUM_PLATING, 0.8, 283.15)}
print(f"committed k_r_cyc = {n._PyCellParams.k_r_cyc}, k_cyc = {n._PyCellParams.k_cyc}")
print(f"{'k_r_cyc':>9}  {'scenario':16s} {'ir_drop':>9} {'target':>9} "
      f"{'dvdq':>9} {'target':>9}   {'max rel err':>11}")
for k in (0.0020, 0.0015, 0.0012, 0.0010, 0.0008):
    n._PyCellParams.k_r_cyc = k
    for lab, (f, sev, T) in SCEN.items():
        recs = run_cycling_campaign(n_cycles=60, fault=f, fault_severity=sev,
                                    temperature_k=T)
        got = {a: mean_of(recs, a, attr=True) for a in ("ir_drop_v", "peak_charge_dvdq")}
        rel = max(abs(got[a] - tgt[lab][a]) / abs(tgt[lab][a]) for a in got)
        print(f"{k:9.4f}  {lab:16s} {got['ir_drop_v']:9.4f} {tgt[lab]['ir_drop_v']:9.4f} "
              f"{got['peak_charge_dvdq']:9.3f} {tgt[lab]['peak_charge_dvdq']:9.3f}   {rel:11.2e}"
              + ("   <== MATCH" if rel < 1e-6 else ""))
