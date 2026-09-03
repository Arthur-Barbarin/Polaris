"""Reproduce every headline number in the Sprint 16 README.

Run:
    python scripts/verify.py

Deterministic — no randomness, no external solver. Solves the default
minimum-energy trajectory problem with the in-house ADMM QP solver and asserts
each headline figure, including the exact 25% bang-bang energy penalty and the
match to the closed-form optimum. Exits non-zero on drift.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from traj import TrajectoryProblem, solve_trajectory, benefit, corridor_sweep   # noqa: E402
from traj.metrics import analytic_rms                                            # noqa: E402


def _check(label: str, value, ok: bool) -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: {value}")
    return ok


def main() -> int:
    print("=== Trajectory Optimization — verification ===")
    ok = True
    p = TrajectoryProblem()

    sol = solve_trajectory(p, include_path_constraints=True)
    b = benefit(p)

    print("\nsolver:")
    ok &= _check("ADMM converged", sol.converged, sol.converged)
    ok &= _check("primal residual < 1e-4", f"{sol.primal_residual:.1e}",
                 sol.primal_residual < 1e-4)
    ok &= _check("dual residual < 1e-4", f"{sol.dual_residual:.1e}",
                 sol.dual_residual < 1e-4)

    print("\nfeasibility:")
    ok &= _check("reaches goal", f"{sol.terminal_error:.2e} m", sol.terminal_error < 1e-2)
    ok &= _check("clears altitude floor", f"{sol.min_floor_clearance:.2f} m",
                 sol.min_floor_clearance > -1e-3)
    ok &= _check("holds noise corridor", f"{sol.min_corridor_clearance:.3f} m",
                 sol.min_corridor_clearance > -1e-3)
    ok &= _check("respects accel envelope", f"{sol.max_accel:.3f} m/s^2",
                 sol.max_accel <= max(p.ax_max, p.ah_max) + 1e-3)

    print("\nbenefit:")
    ok &= _check("saving vs bang-bang ~ 25%", f"{100*b.savings_fraction:.2f}%",
                 abs(b.savings_fraction - 0.25) < 0.01)
    ok &= _check("noise corridor adds energy", f"+{b.price_of_noise:.2f}",
                 b.price_of_noise > 0)

    print("\nanalytic match:")
    rms = analytic_rms(p)
    ok &= _check("unconstrained QP = closed-form optimum", f"RMS {rms:.4f} m", rms < 0.05)

    print("\nmonotonicity:")
    sweep = corridor_sweep(p, [160, 180, 200, 220, 240, 260])
    energies = [e for _, e in sweep]
    mono = all(energies[i] <= energies[i + 1] + 1e-6 for i in range(len(energies) - 1))
    ok &= _check("energy rises with the noise floor", [round(e, 1) for e in energies], mono)

    print("\nreproducibility:")
    e2 = solve_trajectory(p, include_path_constraints=True).energy
    ok &= _check("energy stable across runs", f"{e2:.4f}", abs(e2 - sol.energy) < 1e-6)

    print("\n" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
