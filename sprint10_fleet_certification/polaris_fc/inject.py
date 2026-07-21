"""Fault-injection re-run adapter.

The console's "wow" moment: an operator picks a scenario (a specific fault
family in sprint 8 or 9, or a specific characterisation scenario in
sprint 7), presses "inject", and watches the traceability matrix change
in real time as the source campaign is re-executed against the exact
same test cards.

This module is deliberately *thin*: it re-uses the sprint's own
`run_campaign.py` / `run_cycling_campaign.py` / `benchmark_estimators.py`
so there is no chance the console diverges from what those sprints report
on their own. The subprocess call keeps environments isolated (sprint 8/9
share numpy/scikit-learn but sprint 7 uses different scipy paths).

Design guardrails:
  - Never mutate the artefacts irreversibly: the caller can request a
    scratch output dir so a demo doesn't clobber the checked-in numbers.
  - Time-cap each injection: the sprint 9 campaign at default seeds runs
    long; the console uses --seeds 4 --dt 0.05 by default so an inject
    completes in seconds, not minutes.
  - Return the resulting RollupResult, not stdout, so the UI has structure.
"""
from __future__ import annotations

import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .evidence import RollupResult, build_evidence
from .requirements import Subsystem


@dataclass
class InjectionPlan:
    subsystem: Subsystem
    scenario: str
    label: str          # human-readable, e.g. "GPS dropout (sprint 8, 4 seeds)"
    command: List[str]
    cwd: Path           # sprint working directory
    timeout_s: int = 180


def _sprint_root(repo_root: Path, subsystem: Subsystem) -> Path:
    return repo_root / {
        Subsystem.BATTERY_PACK: "sprint7_battery_testbench",
        Subsystem.FIXED_WING_UAV: "sprint8_flight_test_harness",
        Subsystem.LANDING_MULTIROTOR: "sprint9_precision_landing",
    }[subsystem]


# --- Catalog of injections available in the UI --------------------------------

# Only injections that already exist as top-level scripts in the source
# sprints; the console does not invent new simulator entry points.

def available_injections(repo_root: Path) -> List[InjectionPlan]:
    plans: List[InjectionPlan] = []

    # Sprint 7 — accelerated cycling campaign (fixed scenario set, one
    # command re-runs the whole matrix).
    s7 = _sprint_root(repo_root, Subsystem.BATTERY_PACK)
    plans.append(InjectionPlan(
        subsystem=Subsystem.BATTERY_PACK,
        scenario="cycling_campaign_all_modes",
        label="Battery cycling campaign — HEALTHY + 4 degradation modes",
        command=[sys.executable, "scripts/run_cycling_campaign.py"],
        cwd=s7, timeout_s=240,
    ))

    # Sprint 8 — flight-test campaign with a small seed count so the
    # inject returns quickly during a demo.
    s8 = _sprint_root(repo_root, Subsystem.FIXED_WING_UAV)
    plans.append(InjectionPlan(
        subsystem=Subsystem.FIXED_WING_UAV,
        scenario="flight_campaign_quick",
        label="Fixed-wing campaign — 4 seeds x 8 scenarios (fast demo)",
        command=[sys.executable, "scripts/run_campaign.py",
                 "--seeds", "4", "--dt", "0.05"],
        cwd=s8, timeout_s=300,
    ))

    # Sprint 9 — landing campaign, quick.
    s9 = _sprint_root(repo_root, Subsystem.LANDING_MULTIROTOR)
    plans.append(InjectionPlan(
        subsystem=Subsystem.LANDING_MULTIROTOR,
        scenario="landing_campaign_quick",
        label="Landing campaign — 4 seeds x 10 scenarios (fast demo)",
        command=[sys.executable, "scripts/run_campaign.py",
                 "--seeds", "4", "--dt", "0.05"],
        cwd=s9, timeout_s=300,
    ))
    return plans


# --- Runner -------------------------------------------------------------------

@dataclass
class InjectionResult:
    plan: InjectionPlan
    exit_code: int
    stdout: str
    stderr: str
    rollup: Optional[RollupResult]


def run_injection(plan: InjectionPlan, repo_root: Path,
                  progress: Optional[Callable[[str], None]] = None) -> InjectionResult:
    if progress:
        progress(f"[inject] {plan.label}\n"
                 f"[inject]   cwd={plan.cwd}\n"
                 f"[inject]   cmd={' '.join(shlex.quote(c) for c in plan.command)}\n")
    try:
        proc = subprocess.run(
            plan.command, cwd=str(plan.cwd),
            capture_output=True, text=True, timeout=plan.timeout_s,
        )
        exit_code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        exit_code = -1
        stdout = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = f"TIMEOUT after {plan.timeout_s}s"
    except FileNotFoundError as e:
        exit_code = -2
        stdout, stderr = "", str(e)

    if progress:
        progress(f"[inject] exit={exit_code}\n")

    # Re-read the traceability matrix regardless of exit code — a partial
    # run is still evidence, and the manifest hashes will show what moved.
    rollup = build_evidence(repo_root)
    return InjectionResult(plan=plan, exit_code=exit_code,
                           stdout=stdout, stderr=stderr, rollup=rollup)


def scenarios_by_subsystem(repo_root: Path) -> Dict[Subsystem, List[InjectionPlan]]:
    out: Dict[Subsystem, List[InjectionPlan]] = {}
    for p in available_injections(repo_root):
        out.setdefault(p.subsystem, []).append(p)
    return out
