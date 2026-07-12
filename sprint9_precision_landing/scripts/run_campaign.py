#!/usr/bin/env python3
"""Run the precision-landing campaign: outcomes, CEP dispersion, triage.

For each scenario x seed: simulate -> grade (PASS / FAIL / REJECT / TIMEOUT).
Nominal touchdowns are aggregated into a CEP; a PCA+GMM triage is fit over all
approaches. Results are written to data/ and a summary is printed.

Usage:
    python scripts/run_campaign.py --seeds 20 --dt 0.02
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from polaris_pl import (  # noqa: E402
    ALL_SCENARIOS, CARD_VERSION, LandingTriage, cep, compute_metrics, grade, simulate,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--dt", type=float, default=0.02)
    ap.add_argument("--outdir", default=str(REPO / "data"))
    args = ap.parse_args()
    outdir = Path(args.outdir); outdir.mkdir(exist_ok=True)

    metrics, rows = [], []
    outcomes = defaultdict(lambda: defaultdict(int))
    touchdowns = defaultdict(list)

    for name, fn in ALL_SCENARIOS.items():
        for seed in range(args.seeds):
            log = simulate(fn(), seed=seed, dt=args.dt)
            m = compute_metrics(log)
            r = grade(m)
            metrics.append(m)
            rows.append({"seed": seed, **r.summary_row()})
            outcomes[name][r.outcome] += 1
            if log.outcome == "LANDED":
                touchdowns[name].append([log.touchdown_x, log.touchdown_y])

    # CEP per scenario that produces landings.
    cep_by_scen = {}
    for name, pts in touchdowns.items():
        if pts:
            c = cep(np.array(pts))
            cep_by_scen[name] = {"n": c.n, "cep50": c.cep50, "cep95": c.cep95,
                                 "ellipse_a": c.ellipse_a, "ellipse_b": c.ellipse_b,
                                 "ellipse_angle": c.ellipse_angle,
                                 "mean_x": c.mean_x, "mean_y": c.mean_y}

    tri = LandingTriage(n_components=6, n_clusters=16).fit(metrics)
    results = tri.predict(metrics)
    acc = LandingTriage.accuracy(results)
    per_class = defaultdict(lambda: [0, 0])
    for r in results:
        per_class[r.label][1] += 1
        per_class[r.label][0] += int(r.predicted_mode == r.label)

    (outdir / "campaign.json").write_text(json.dumps(
        {"card_version": CARD_VERSION, "seeds": args.seeds, "dt": args.dt,
         "runs": rows, "cep": cep_by_scen}, indent=2))
    (outdir / "triage.json").write_text(json.dumps(
        {"overall_accuracy": acc, "per_class": dict(per_class)}, indent=2))

    print(f"\nPrecision-landing campaign  (card v{CARD_VERSION}, "
          f"{args.seeds} seeds/scenario, dt={args.dt}s)\n")
    print(f"{'scenario':16s} {'PASS':>4s} {'FAIL':>4s} {'REJ':>4s} {'T/O':>4s}  "
          f"{'CEP50[m]':>9s} {'CEP95[m]':>9s}")
    for name in ALL_SCENARIOS:
        o = outcomes[name]
        c = cep_by_scen.get(name, {})
        c50 = f"{c['cep50']:.3f}" if c else "  -"
        c95 = f"{c['cep95']:.3f}" if c else "  -"
        print(f"{name:16s} {o['PASS']:>4d} {o['FAIL']:>4d} {o['REJECT']:>4d} "
              f"{o['TIMEOUT']:>4d}  {c50:>9s} {c95:>9s}")

    print(f"\nTriage overall accuracy (in-sample): {acc:.1%}")
    for lbl, (c, n) in sorted(per_class.items()):
        print(f"  {lbl:16s} {c}/{n}")
    print(f"\nWrote {outdir/'campaign.json'} and {outdir/'triage.json'}")


if __name__ == "__main__":
    main()
