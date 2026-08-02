"""Reproduce every headline number in the Sprint 12 README.

Run:
    python scripts/verify.py

Drives the deterministic agent end-to-end against the checked-in Sprint 7-11
artefacts and asserts each headline figure. Exits non-zero if any check
fails. No network, no API key — the deterministic policy makes the agent
byte-for-byte reproducible.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from polaris_agent import Agent, DeterministicPolicy, build_registry     # noqa: E402
from polaris_agent import render_findings_report                          # noqa: E402


def _check(label: str, value, ok: bool) -> bool:
    print(f"  {'✓' if ok else '✗'} {label}: {value}")
    return ok


def _run(basis: str):
    reg = build_registry(basis=basis)
    return Agent(registry=reg, policy=DeterministicPolicy()).run("verify")


def main() -> int:
    print("=== Agentic V&V Analyst — verification ===")
    ok = True

    # --- Baseline: clean GO, no findings -------------------------------------
    base = _run("baseline")
    print("\nbaseline basis (ratified catalog):")
    ok &= _check("fleet status", base.ctx.fleet_status(),
                 base.ctx.fleet_status() == "GREEN")
    ok &= _check("findings", len(base.ctx.findings),
                 len(base.ctx.findings) == 0)
    ok &= _check("agent finalized cleanly", base.stopped_reason,
                 base.stopped_reason == "finalized")
    ok &= _check("all tool calls succeeded",
                 sum(1 for s in base.transcript if s.error),
                 all(s.error is None for s in base.transcript))

    # --- Stress: two findings, one blocker, NO-GO ----------------------------
    strs = _run("stress")
    ids = {f.requirement_id for f in strs.ctx.findings}
    print("\nstress basis (tightened thresholds):")
    ok &= _check("fleet status", strs.ctx.fleet_status(),
                 strs.ctx.fleet_status() == "BLOCKED")
    ok &= _check("finding set", sorted(ids),
                 ids == {"FC-BAT-001", "FC-LDG-001"})
    n_block = sum(1 for f in strs.ctx.findings
                  if strs.ctx.is_blocking(strs.ctx.result_for(f.requirement_id)))
    ok &= _check("blocking findings", n_block, n_block == 1)

    # --- Grounding invariant: measurement is basis-independent ---------------
    def _val(res, rid):
        return res.ctx.view(res.ctx.result_for(rid))["measured_value"]
    same = _val(base, "FC-BAT-001") == _val(strs, "FC-BAT-001")
    print("\ngrounding invariant:")
    ok &= _check("FC-BAT-001 measured value identical across bases",
                 _val(strs, "FC-BAT-001"), same)

    # --- Reproducibility: identical tool-call sequence -----------------------
    strs2 = _run("stress")
    seq1 = [(s.tool, s.arguments) for s in strs.transcript]
    seq2 = [(s.tool, s.arguments) for s in strs2.transcript]
    print("\nreproducibility:")
    ok &= _check("stress tool-call sequence stable across runs",
                 f"{len(seq1)} steps", seq1 == seq2)

    # --- Report renders and states the decision ------------------------------
    md = render_findings_report(strs)
    print("\nreport:")
    ok &= _check("report states NO-GO", "NO-GO in report", "NO-GO" in md)
    ok &= _check("report binds real value 0.03884",
                 "present", "0.03884" in md)

    print("\n" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
