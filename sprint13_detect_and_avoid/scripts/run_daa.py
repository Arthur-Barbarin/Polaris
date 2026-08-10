"""Detect-and-Avoid Studio — command-line entry point.

Two things a visitor should try:

    # 1. Watch a single head-on encounter resolve, step by step.
    python scripts/run_daa.py single --headon

    # 2. Run a Monte-Carlo campaign and print the safety metrics.
    python scripts/run_daa.py campaign --n 2000 --seed 13

Add ``--surveillance 926`` to a campaign to model a limited-range sensor
(0.5 NM) and watch residual collision risk appear.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from daa import (                                                      # noqa: E402
    State,
    Encounter,
    encounter_set,
    run_campaign,
    simulate_encounter,
    select_ra,
    DWC,
)
from daa.metrics import SimParams                                       # noqa: E402
from daa.wellclear import FT                                           # noqa: E402

NM = 1852.0  # metres per nautical mile


def _headon_encounter() -> Encounter:
    """A canonical co-altitude head-on: two 50 m/s aircraft, 6 km apart."""
    own = State(0.0, 0.0, 0.0, 0.0, 50.0, 0.0)        # heading North
    intr = State(0.0, 6000.0, 0.0, 0.0, -50.0, 0.0)   # heading South, closing
    return Encounter(own, intr, encounter_id=-1)


def cmd_single(args: argparse.Namespace) -> int:
    if args.headon:
        enc = _headon_encounter()
        label = "canonical head-on (50 m/s each, 6 km, co-altitude)"
    else:
        enc = encounter_set(args.index + 1, seed=args.seed)[args.index]
        label = f"encounter #{args.index} from seed {args.seed}"

    print(f"=== Detect-and-Avoid — single encounter ===\n{label}\n")

    un = simulate_encounter(enc, equipped=False)
    eq = simulate_encounter(enc, equipped=True)

    def _line(tag: str, o) -> None:
        verdict = "NMAC" if o.nmac else ("LoWC" if o.lowc else "clear")
        print(f"  {tag:12s} min horiz {o.min_horizontal:6.0f} m   "
              f"min vert {o.min_vertical:5.0f} m   slant {o.min_slant:6.0f} m   -> {verdict}")

    _line("UNEQUIPPED", un)
    _line("EQUIPPED", eq)
    print()
    if eq.alerted:
        print(f"  DAA alerted {eq.alert_lead:.1f} s before CPA and issued: {eq.ra_name}")
    else:
        print("  DAA did not alert (encounter stayed well clear).")
    if un.nmac and not eq.nmac:
        print("  => Baseline collision geometry RESOLVED by the resolution advisory.")
    print(f"\n  Well Clear thresholds (DO-365): DMOD/HMD {DWC.dmod/FT:.0f} ft, "
          f"tau_mod {DWC.taumod_thr:.0f} s, ZTHR {DWC.zthr/FT:.0f} ft")
    return 0


def _print_campaign(title: str, r) -> None:
    print(f"\n--- {title} ---")
    print(f"  encounters                 {r.n}")
    print(f"  NMAC  unequipped           {r.nmac_unequipped:5d}  ({100*r.nmac_rate_unequipped:5.2f}%)")
    print(f"  NMAC  equipped             {r.nmac_equipped:5d}  ({100*r.nmac_rate_equipped:5.2f}%)")
    rr = r.risk_ratio
    print(f"  risk ratio (eq/uneq)       {('  nan' if math.isnan(rr) else f'{rr:6.3f}')}")
    print(f"  LoWC  unequipped           {100*r.lowc_rate_unequipped:5.1f}%")
    print(f"  LoWC  equipped             {100*r.lowc_rate_equipped:5.1f}%")
    print(f"  baseline NMACs resolved    {r.resolved_nmacs}/{r.resolved_nmacs + r.unresolved_nmacs}")
    print(f"  median alert lead time     {r.median_alert_lead:5.1f} s")
    print(f"  equipped min-sep 5th pct   {r.min_sep_equipped_p05:5.0f} m")
    print(f"  RA usage                   {r.ra_counts}")


def cmd_campaign(args: argparse.Namespace) -> int:
    enc = encounter_set(args.n, seed=args.seed)
    print(f"=== Detect-and-Avoid — Monte-Carlo campaign ===")
    print(f"{args.n} encounters, seed {args.seed}")

    nominal = run_campaign(enc)
    _print_campaign("NOMINAL (perfect surveillance)", nominal)

    if args.surveillance and math.isfinite(args.surveillance):
        stress = run_campaign(enc, sim=SimParams(surveillance_range=args.surveillance))
        _print_campaign(f"DEGRADED (sensor range {args.surveillance:.0f} m "
                        f"= {args.surveillance/NM:.2f} NM)", stress)

    if args.report:
        from scripts.report import write_report  # local import to keep CLI light
        path = Path(args.report)
        stress = run_campaign(enc, sim=SimParams(surveillance_range=926.0))
        write_report(path, args.n, args.seed, nominal, stress)
        print(f"\nwrote {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Detect-and-Avoid Studio")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("single", help="run one encounter and print the timeline")
    s.add_argument("--headon", action="store_true", help="use the canonical head-on")
    s.add_argument("--seed", type=int, default=13)
    s.add_argument("--index", type=int, default=0)
    s.set_defaults(func=cmd_single)

    c = sub.add_parser("campaign", help="run a Monte-Carlo campaign")
    c.add_argument("--n", type=int, default=2000)
    c.add_argument("--seed", type=int, default=13)
    c.add_argument("--surveillance", type=float, default=926.0,
                   help="degraded sensor range in m (0.5 NM = 926); set 0 to skip")
    c.add_argument("--report", type=str, default=None, help="write a markdown report here")
    c.set_defaults(func=cmd_campaign)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
