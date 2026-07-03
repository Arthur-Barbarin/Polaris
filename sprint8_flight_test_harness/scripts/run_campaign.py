#!/usr/bin/env python3
"""Run the full fault-injection flight-test campaign.

For each scenario x seed: simulate -> grade against the versioned test cards.
Then fit the PCA+GMM triage over all runs. Results are written to data/ and a
summary table is printed.

Usage:
    python scripts/run_campaign.py --seeds 8 --dt 0.05
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from polaris_ft import (  # noqa: E402
    ALL_SCENARIOS, CARD_VERSION, FlightTriage, compute_metrics, grade, simulate,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--dt", type=float, default=0.05)
    ap.add_argument("--outdir", default=str(REPO / "data"))
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(exist_ok=True)

    metrics = []
    reports = []
    pass_counts = defaultdict(lambda: [0, 0])

    for name, fn in ALL_SCENARIOS.items():
        for seed in range(args.seeds):
            log = simulate(fn(), seed=seed, dt=args.dt)
            m = compute_metrics(log)
            r = grade(m)
            metrics.append(m)
            reports.append({"seed": seed, **r.summary_row()})
            pass_counts[name][1] += 1
            pass_counts[name][0] += int(r.passed)

    # --- Triage over the whole campaign ---
    n_clusters = max(8, len(ALL_SCENARIOS) + 3)
    tri = FlightTriage(n_components=4, n_clusters=n_clusters).fit(metrics)
    results = tri.predict(metrics)
    acc = FlightTriage.accuracy(results)

    per_class = defaultdict(lambda: [0, 0])
    for r in results:
        per_class[r.label][1] += 1
        per_class[r.label][0] += int(r.predicted_mode == r.label)

    # --- Persist ---
    (outdir / "campaign.json").write_text(json.dumps({
        "card_version": CARD_VERSION,
        "seeds": args.seeds,
        "dt": args.dt,
        "runs": reports,
    }, indent=2))
    (outdir / "triage.json").write_text(json.dumps({
        "overall_accuracy": acc,
        "per_class": {k: v for k, v in per_class.items()},
        "predictions": [
            {"label": r.label, "predicted": r.predicted_mode,
             "cluster": r.cluster, "posterior": round(r.posterior, 3)}
            for r in results
        ],
    }, indent=2))

    # --- Print summary ---
    print(f"\nFlight-test campaign  (card v{CARD_VERSION}, "
          f"{args.seeds} seeds/scenario, dt={args.dt}s)\n")
    print(f"{'scenario':16s} {'pass':>7s}  {'xt_rms':>7s} {'xt_max':>7s} "
          f"{'alt_rms':>7s} {'Va_rms':>7s} {'navRMSE':>7s} {'settle':>7s}")
    by_scen = defaultdict(list)
    for m in metrics:
        by_scen[m.scenario].append(m)
    for name in ALL_SCENARIOS:
        ms = by_scen[name]
        avg = lambda k: sum(getattr(x, k) for x in ms) / len(ms)
        p = pass_counts[name]
        st = [x.settling_time_s for x in ms if x.settling_time_s == x.settling_time_s]
        st_avg = sum(st) / len(st) if st else float("nan")
        print(f"{name:16s} {p[0]:>3d}/{p[1]:<3d}  {avg('cross_track_rms'):7.2f} "
              f"{avg('cross_track_max'):7.2f} {avg('alt_hold_rms'):7.2f} "
              f"{avg('airspeed_hold_rms'):7.2f} {avg('est_pos_rmse'):7.2f} "
              f"{st_avg:7.1f}")

    print(f"\nTriage overall accuracy: {acc:.1%}")
    for lbl, (c, n) in sorted(per_class.items()):
        print(f"  {lbl:16s} {c}/{n}")
    print(f"\nWrote {outdir/'campaign.json'} and {outdir/'triage.json'}")


if __name__ == "__main__":
    main()
