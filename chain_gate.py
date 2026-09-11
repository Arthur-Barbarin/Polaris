#!/usr/bin/env python3
"""Run every suite in the S7 -> S12 evidence chain, plus each sprint's own
verification script, and fail if any of them does.

WHY THIS EXISTS
---------------
Sprints 10 and 12 do not re-run any simulator. They read the versioned JSON
artefacts that Sprints 7, 8 and 9 write. A change that is correct and fully
tested inside one sprint can therefore break a downstream requirement without
any single sprint's suite noticing.

That is not hypothetical. On 2026-09-06 a genuine defect was fixed in Sprint
7's estimator benchmark; the fix moved a number that Sprint 10 grades a
requirement against, which cascaded into five Sprint 12 failures. Only Sprints
7 and 8 were re-run, so the regression was pushed. See
integration_campaign_2026-09, finding F2-4.

Run this before pushing anything that touches a sprint's `data/` directory,
its model coefficients, or any field a downstream sprint reads.

    python chain_gate.py            # everything
    python chain_gate.py --quick    # suites only, skip the verify scripts
    python chain_gate.py --only sprint9_precision_landing
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Ordered upstream -> downstream, so the first failure is the most likely cause.
CHAIN = [
    # S7 has no read-only verify script: scripts/run_all.sh REGENERATES data/,
    # and a gate must never mutate the artefacts it is checking. S7's own
    # tests/test_dataset_reproducibility.py already asserts that the committed
    # dataset is reproducible from the model, which is the property that matters.
    ("sprint7_battery_testbench", []),
    ("sprint8_flight_test_harness", ["scripts/verify.py"]),
    ("sprint9_precision_landing", ["scripts/verify.py"]),
    ("sprint10_fleet_certification", ["scripts/verify.py"]),
    ("sprint12_vv_agent", []),
]


def run(cmd: list[str], cwd: Path, timeout: int = 900) -> tuple[bool, str, float]:
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout)
        return p.returncode == 0, (p.stdout + p.stderr), time.time() - t0
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s", time.time() - t0
    except FileNotFoundError as e:
        return False, f"not runnable: {e}", time.time() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="run the pytest suites only, skip the verify scripts")
    ap.add_argument("--only", action="append", default=None,
                    help="restrict to one or more sprint directories")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    py = sys.executable
    results: list[tuple[str, str, bool, float]] = []

    for sprint, extras in CHAIN:
        if args.only and sprint not in args.only:
            continue
        d = ROOT / sprint
        if not d.is_dir():
            results.append((sprint, "MISSING", False, 0.0))
            continue

        if (d / "tests").is_dir():
            ok, out, dt = run([py, "-m", "pytest", "-q"], d, args.timeout)
            results.append((sprint, "pytest", ok, dt))
            if not ok:
                print(f"\n===== {sprint} pytest FAILED =====\n{out[-4000:]}")

        if args.quick:
            continue
        for script in extras:
            path = d / script
            if not path.is_file():
                continue
            cmd = ["bash", script] if script.endswith(".sh") else [py, script]
            ok, out, dt = run(cmd, d, args.timeout)
            results.append((sprint, script, ok, dt))
            if not ok:
                print(f"\n===== {sprint} {script} FAILED =====\n{out[-4000:]}")

    width = max(len(s) for s, *_ in results) if results else 10
    print("\n=== S7 -> S12 chain gate ===")
    for sprint, what, ok, dt in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {sprint:<{width}}  {what:<18} {dt:6.1f}s")

    failed = [(s, w) for s, w, ok, _ in results if not ok]
    if failed:
        print(f"\n{len(failed)} of {len(results)} checks FAILED: "
              + ", ".join(f"{s}/{w}" for s, w in failed))
        print("A downstream failure with green upstream suites usually means an "
              "artefact under data/ moved. Check what the upstream sprint last "
              "regenerated before assuming the downstream sprint is at fault.")
        return 1
    print(f"\nall {len(results)} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
