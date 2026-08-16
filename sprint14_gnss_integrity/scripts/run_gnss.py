"""GNSS Integrity Monitor — command-line entry point.

Two things a visitor should try:

    # 1. Screen one spoofing attack and watch RAIM miss it while the monitor catches it.
    python scripts/run_gnss.py single --scenario spoof

    # 2. Run the Monte-Carlo threat campaign and read the integrity table.
    python scripts/run_gnss.py campaign --n 2000 --seed 14
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from gnss import (                                                     # noqa: E402
    MeasurementParams, RaimParams, SpoofParams,
    nominal, single_fault, spoof, jamming,
    ls_solve, detect, exclude, protection_level, screen, dop,
    run_campaign,
)

_BUILDERS = {"nominal": nominal, "fault": single_fault,
             "spoof": spoof, "jamming": jamming}


def cmd_single(args: argparse.Namespace) -> int:
    rng = np.random.default_rng(args.seed)
    for _ in range(args.index + 1):
        scn = _BUILDERS[args.scenario](rng, MeasurementParams())
    rp, sp = RaimParams(), SpoofParams()

    sol = ls_solve(scn.H, scn.z)
    det = detect(scn, rp)
    ex = exclude(scn, rp)
    pl = protection_level(scn.H, scn.sigma, rp)
    st = screen(scn, rp, sp)
    d = dop(scn.H)
    herr = float(np.hypot(*sol.horizontal))

    print(f"=== GNSS Integrity — single scenario: {scn.kind} ===")
    print(f"  satellites {len(scn.sats)}   HDOP {d['HDOP']:.2f}   sigma {scn.sigma:.1f} m")
    print(f"  horizontal position error (computed vs truth): {herr:6.1f} m")
    print(f"\n  RAIM detection:   SSE/sigma^2 {det.sse/scn.sigma**2:7.2f}  "
          f"vs threshold {det.threshold/scn.sigma**2:6.2f}  -> "
          f"{'DETECTED' if det.detected else 'no fault'}")
    if ex.detected and ex.excluded_sv is not None:
        tag = "correct" if ex.correct else ("wrong" if ex.correct is not None else "n/a")
        after = float(np.hypot(*ex.sol_after.horizontal)) if ex.sol_after is not None else float("nan")
        print(f"  exclusion:        removed SV {ex.excluded_sv} ({tag}); "
              f"error {herr:.1f} -> {after:.1f} m")
    print(f"  protection level: HPL {pl.hpl:6.1f} m  vs HAL {rp.hal:.0f} m  -> "
          f"{'AVAILABLE' if pl.available else 'UNAVAILABLE'}")
    print(f"\n  spoof/jam screen: mean C/N0 {st.mean_cn0:.1f} dB-Hz (std {st.cn0_std:.2f}), "
          f"innovation d^2 {st.mahalanobis:.1f}")
    flags = []
    if st.raim_detected: flags.append("RAIM")
    if st.jam_flag: flags.append("JAMMING")
    if st.cn0_spoof_flag: flags.append("SPOOF(C/N0)")
    if st.innovation_flag: flags.append("SPOOF(jump)")
    print(f"  flags raised:     {', '.join(flags) if flags else 'none'}")
    print(f"  VERDICT:          {'TRUSTWORTHY' if st.trustworthy else 'FIX REJECTED'}")
    if scn.kind == "spoof" and not st.raim_detected and not st.trustworthy:
        print("  => RAIM alone would have TRUSTED this spoofed fix; the monitor caught it.")
    return 0


def _print_campaign(r) -> None:
    p = r.params
    print(f"\nconfig: Pfa {p['pfa']:.0e}, Pmd {p['pmd']:.0e}, HAL {p['hal']:.0f} m, "
          f"sigma {p['sigma']:.1f} m\n")
    print("NOMINAL (fault-free)")
    print(f"  false-alarm rate (full screen)   {r.fa_rate_full:.4f}")
    print(f"  false-alarm rate (RAIM only)     {r.fa_rate_raim:.4f}")
    print(f"  availability (HPL < HAL)         {r.availability:.3f}   median HPL {r.median_hpl:.0f} m")
    print("\nSINGLE FAULT (step bias on one satellite)")
    print(f"  detection rate                   {r.sf_detect_rate:.3f}")
    print(f"  correct-exclusion rate           {r.sf_exclude_correct_rate:.3f}")
    print(f"  horiz error before -> after FDE  {r.sf_err_before:.1f} -> {r.sf_err_after:.1f} m")
    print(f"  HMI events (missed, err>HAL)     {r.sf_hmi_raim}")
    print("\nSPOOF (coordinated, residual-clean)   <-- headline")
    print(f"  detection: RAIM only             {r.spoof_detect_raim:.3f}")
    print(f"  detection: full monitor          {r.spoof_detect_full:.3f}")
    print(f"  HMI events: RAIM only            {r.spoof_hmi_raim}")
    print(f"  HMI events: full monitor         {r.spoof_hmi_full}")
    print("\nJAMMING (depressed C/N0)")
    print(f"  detection rate                   {r.jam_detect_rate:.3f}")


def cmd_campaign(args: argparse.Namespace) -> int:
    r = run_campaign(args.n, seed=args.seed)
    print(f"=== GNSS Integrity — Monte-Carlo campaign ===")
    print(f"{args.n} scenarios per threat family, seed {args.seed}")
    _print_campaign(r)
    if args.report:
        from scripts.report import write_report
        path = Path(args.report)
        write_report(path, args.n, args.seed, r)
        print(f"\nwrote {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="GNSS Integrity Monitor")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("single", help="screen one scenario")
    s.add_argument("--scenario", choices=list(_BUILDERS), default="spoof")
    s.add_argument("--seed", type=int, default=14)
    s.add_argument("--index", type=int, default=0)
    s.set_defaults(func=cmd_single)

    c = sub.add_parser("campaign", help="run the Monte-Carlo threat campaign")
    c.add_argument("--n", type=int, default=2000)
    c.add_argument("--seed", type=int, default=14)
    c.add_argument("--report", type=str, default=None)
    c.set_defaults(func=cmd_campaign)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
