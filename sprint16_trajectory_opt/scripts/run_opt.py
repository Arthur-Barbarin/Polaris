"""Trajectory Optimization Studio — command-line entry point.

Two things a visitor should try:

    # 1. Solve the eVTOL descent and see the numbers that matter.
    python scripts/run_opt.py solve

    # 2. Sweep the noise-abatement floor and watch the energy price rise.
    python scripts/run_opt.py sweep
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from traj import TrajectoryProblem, solve_trajectory, benefit, corridor_sweep   # noqa: E402
from traj.metrics import analytic_rms                                            # noqa: E402


def cmd_solve(args: argparse.Namespace) -> int:
    p = TrajectoryProblem()
    sol = solve_trajectory(p, include_path_constraints=True)
    b = benefit(p)
    print("=== Trajectory Optimization — minimum-energy eVTOL descent ===")
    print(f"  start [x,vx,h,vh] = {p.x0.tolist()}   goal = {p.xg.tolist()}   T = {p.T:.0f} s")
    print(f"  QP: {p.N} steps, {2*p.N} control vars; ADMM {sol.iterations} iters, "
          f"converged={sol.converged} (primal {sol.primal_residual:.1e}, dual {sol.dual_residual:.1e})")
    print()
    print(f"  control energy (optimal)         {sol.energy:8.2f}")
    print(f"  vs bang-bang baseline            {b.energy_bangbang:8.2f}   "
          f"-> {100*b.savings_fraction:.1f}% less energy")
    print(f"  price of the noise corridor      +{b.price_of_noise:7.2f}   "
          f"({100*b.price_of_noise/b.energy_optimal:.1f}% over unconstrained optimum)")
    print()
    print(f"  terminal error                   {sol.terminal_error:8.2e} m")
    print(f"  altitude range on path           {sol.X[:,2].min():.1f} – {sol.X[:,2].max():.1f} m")
    print(f"  min floor clearance (>= 0)       {sol.min_floor_clearance:8.2f} m")
    print(f"  min corridor clearance (>= 0)    {sol.min_corridor_clearance:8.3f} m")
    print(f"  peak |accel| / limit             {sol.max_accel:.3f} / "
          f"{max(p.ax_max,p.ah_max):.1f} m/s^2")
    print(f"  feasible                         {sol.feasible}")
    print(f"\n  analytic check (unconstrained vs closed-form): RMS "
          f"{analytic_rms(p):.4f} m")
    return 0


def cmd_sweep(args: argparse.Namespace) -> int:
    p = TrajectoryProblem()
    print("=== Trajectory Optimization — noise-corridor energy sweep ===")
    print(f"  raising the required altitude over the noise-sensitive segment\n")
    print("  h_noise (m)   optimal energy")
    prev = None
    for hv, e in corridor_sweep(p, [160, 180, 200, 220, 240, 260]):
        arrow = "" if prev is None else ("  (+%.2f)" % (e - prev))
        print(f"     {hv:6.0f}       {e:8.2f}{arrow}")
        prev = e
    print("\n  Energy rises monotonically as the community-noise floor tightens — "
          "the quantified cost of flying higher over the town.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Trajectory Optimization Studio")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("solve", help="solve the default trajectory problem")
    s.set_defaults(func=cmd_solve)
    w = sub.add_parser("sweep", help="sweep the noise-corridor altitude")
    w.set_defaults(func=cmd_sweep)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
