"""S7 native-vs-pure-Python parity probe (Phase 0 of the S7->S12 integration campaign).

polaris_bms/native.py claims the pure-Python fallback is "numerically equivalent
to the C++ core". S7's pytest suite never exercises the C++ path, so that claim
has never been executed. This probe runs one deterministic scenario through
whichever backend the module selected and prints the result as JSON.

Run it twice and diff:
    python tools/s7_parity_probe.py                        # native  (.so loaded)
    PYTHONPATH=/tmp/fakedarwin python tools/s7_parity_probe.py   # pure-Python mirror
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sprint7_battery_testbench"))

from polaris_bms import native as n  # noqa: E402

out = {
    "backend": "native" if n.native_available() else "pure_python",
    "cell_class": n.Cell.__name__,
    "ekf_class": n.Ekf.__name__,
}

# 1. OCV table lookup / interpolation
out["ocv"] = [n.ocv_of_soc(s / 20.0) for s in range(21)]

# 2. Cell model: 1C discharge at three temperatures, 600 s at dt=1 s
cell_runs = {}
for T in (263.15, 283.15, 298.15, 313.15):
    c = n.Cell(1.0, T)
    v = []
    for k in range(600):
        v.append(c.step(3.2, 1.0))
    snap = c.snapshot()
    cell_runs[f"{T:.2f}"] = {
        "v_first": v[0], "v_mid": v[299], "v_last": v[-1],
        "v_sum": sum(v),
        "snapshot": [snap.soc, snap.v_rc1, snap.v_rc2, snap.T_k,
                     snap.cycles_eq, snap.time_s, snap.q_now_ah, snap.r0_now],
    }
out["cell"] = cell_runs

# 3. Cell model under each fault mode, 300 s at dt=1 s
fault_runs = {}
for f in n.Fault:
    c = n.Cell(0.9, 298.15)
    c.set_fault(f, 0.7)
    v = [c.step(2.0, 1.0) for _ in range(300)]
    snap = c.snapshot()
    fault_runs[f.name] = {"v_last": v[-1], "v_sum": sum(v), "soc": snap.soc, "r0_now": snap.r0_now}
out["fault"] = fault_runs

# 4. EKF: deliberately wrong initial guess, driven by the cell model's own voltage
c = n.Cell(0.80, 298.15)
e = n.Ekf(0.50, 0.05)
soc_hat, soc_true = [], []
for k in range(1200):
    i_a = 3.2 * math.sin(k / 90.0) + 1.0
    v = c.step(i_a, 1.0)
    soc_hat.append(e.step(i_a, v, 298.15, 1.0))
    soc_true.append(c.snapshot().soc)
err = [a - b for a, b in zip(soc_hat, soc_true)]
out["ekf"] = {
    "soc_hat_first": soc_hat[0], "soc_hat_last": soc_hat[-1],
    "soc_true_last": soc_true[-1],
    "variance_last": e.soc_variance,
    "rms_err": math.sqrt(sum(x * x for x in err) / len(err)),
    "max_abs_err": max(abs(x) for x in err),
}

json.dump(out, sys.stdout, indent=1, sort_keys=True)
print()
