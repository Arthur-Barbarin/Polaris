"""Phase 1: the shipped S7 dataset is not reproducible from the committed model.

Hypothesis under test: data/cycle_records.json was generated with a cycle-fade
coefficient k_cyc = 0.0030, while cpp/cell_model.hpp (and the Python mirror)
now carry k_cyc = 0.0090 -- a factor of 3.

Method: force the pure-Python backend (so k_cyc is patchable from Python),
re-run the campaign at several k_cyc values, and compare the resulting SoH
trace against the shipped dataset. Nothing is written to the repository.
"""
import json, sys
from pathlib import Path

S7 = Path(__file__).resolve().parents[2] / "sprint7_battery_testbench"
sys.path.insert(0, str(S7))

import platform
platform.system = lambda: "Darwin"          # force the pure-Python mirror

from polaris_bms import native as n
assert not n.native_available(), "expected the pure-Python path"

from polaris_bms.cycler import run_cycling_campaign
from polaris_bms import Fault

SHIPPED = json.load(open(S7 / "data" / "cycle_records.json"))
ship = {lab: [r["soh_pct"] for r in SHIPPED if r["fault"] == lab]
        for lab in ("HEALTHY", "LITHIUM_PLATING")}

SCEN = {"HEALTHY": (Fault.NONE, 0.0, 298.15),
        "LITHIUM_PLATING": (Fault.LITHIUM_PLATING, 0.8, 283.15)}

print(f"committed k_cyc = {n._PyCellParams.k_cyc}")
print(f"{'k_cyc':>8}  {'scenario':16s} {'soh[1]':>9} {'soh[60]':>9}   "
      f"{'shipped soh[1]':>14} {'shipped soh[60]':>15}  {'max |err|':>10}")
for k in (0.0090, 0.0040, 0.0030, 0.0025):
    n._PyCellParams.k_cyc = k
    for lab, (f, sev, T) in SCEN.items():
        recs = run_cycling_campaign(n_cycles=60, fault=f, fault_severity=sev,
                                    temperature_k=T)
        got = [r.soh_pct for r in recs]
        err = max(abs(a - b) for a, b in zip(got, ship[lab]))
        print(f"{k:8.4f}  {lab:16s} {got[0]:9.3f} {got[-1]:9.3f}   "
              f"{ship[lab][0]:14.3f} {ship[lab][-1]:15.3f}  {err:10.4f}"
              f"{'   <== MATCH' if err < 1e-6 else ''}")
