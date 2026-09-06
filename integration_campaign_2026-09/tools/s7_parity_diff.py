"""Numeric diff of the two s7_parity_probe.py runs. Reports the worst relative
and absolute deviation per section, and every field whose relative deviation
exceeds 1e-12 (well inside double-precision round-off for these magnitudes)."""
import json, sys

a = json.load(open("logs/s7_native.json"))
b = json.load(open("logs/s7_pyfallback.json"))
print(f"A = {a['backend']:12s} Cell={a['cell_class']:12s} Ekf={a['ekf_class']}")
print(f"B = {b['backend']:12s} Cell={b['cell_class']:12s} Ekf={b['ekf_class']}")
print()

TOL = 1e-12
rows = []
worst = {s: (0.0, 0.0, '(all fields bit-identical)', 0.0, 0.0) for s in ('ocv', 'cell', 'fault', 'ekf')}

def walk(pa, pb, path):
    if isinstance(pa, dict):
        for k in pa:
            walk(pa[k], pb[k], path + [str(k)])
    elif isinstance(pa, list):
        for i, (x, y) in enumerate(zip(pa, pb)):
            walk(x, y, path + [str(i)])
    elif isinstance(pa, (int, float)):
        d = abs(pa - pb)
        r = d / max(abs(pa), abs(pb), 1e-300)
        sec = path[0]
        if r >= worst[sec][0]:
            worst[sec] = (r, d, ".".join(path), pa, pb)
        if r > TOL:
            rows.append((r, d, ".".join(path), pa, pb))

for sec in ("ocv", "cell", "fault", "ekf"):
    walk(a[sec], b[sec], [sec])

print("worst relative deviation per section")
for sec in ("ocv", "cell", "fault", "ekf"):
    r, d, p, x, y = worst[sec]
    print(f"  {sec:6s} rel={r:.3e}  abs={d:.3e}  at {p}")
print()
print(f"fields exceeding rel tol {TOL:g}: {len(rows)}")
for r, d, p, x, y in sorted(rows, reverse=True)[:25]:
    print(f"  rel={r:.6e} abs={d:.6e}  {p}\n      native={x!r}\n      python={y!r}")
sys.exit(0)
