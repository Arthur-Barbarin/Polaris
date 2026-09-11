"""Agent-loop tests: termination, reproducibility, guardrails."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from polaris_agent import Agent, DeterministicPolicy, build_registry


def _run(basis="baseline", subsystems=None):
    reg = build_registry(basis=basis)
    agent = Agent(registry=reg, policy=DeterministicPolicy(subsystems=subsystems))
    return agent.run("goal")


def test_agent_terminates_by_finalizing():
    res = _run("baseline")
    assert res.stopped_reason == "finalized"
    assert res.transcript[-1].tool == "finalize"
    assert res.n_steps < 40                    # well under the step budget


def test_baseline_surfaces_the_known_estimator_finding():
    # FC-BAT-005 is a deliberate, tracked finding on the baseline basis: under a
    # pure current-shunt bias with a correct seed the EKF is worse than the
    # coulomb counter it replaces. It was split out of FC-BAT-002 on 2026-09-11
    # precisely so it could not be averaged away. The fleet is therefore
    # legitimately FINDINGS, not GREEN, and the analyst must surface it.
    # See integration_campaign_2026-09 finding F2-4 and FA-002 rev B.
    res = _run("baseline")
    assert {f.requirement_id for f in res.ctx.findings} == {"FC-BAT-005"}
    assert res.ctx.fleet_status() == "FINDINGS"
    # MAJOR, so it is a finding to disposition, never a certification blocker
    f = res.ctx.findings[0]
    assert f.disposition != "BLOCKER"


def test_stress_produces_expected_findings_and_no_go():
    res = _run("stress")
    ids = {f.requirement_id for f in res.ctx.findings}
    # FC-BAT-005 fails on every basis; the stress basis adds two more.
    assert ids == {"FC-BAT-001", "FC-LDG-001", "FC-BAT-005"}
    assert res.ctx.fleet_status() == "BLOCKED"
    # the blocker must be dispositioned as such
    ldg = next(f for f in res.ctx.findings if f.requirement_id == "FC-LDG-001")
    assert ldg.disposition == "BLOCKER"


def test_deterministic_policy_is_reproducible():
    """Two independent runs produce an identical tool-call sequence."""
    a = _run("stress")
    b = _run("stress")
    seq_a = [(s.tool, s.arguments) for s in a.transcript]
    seq_b = [(s.tool, s.arguments) for s in b.transcript]
    assert seq_a == seq_b


def test_no_tool_call_errors_on_happy_path():
    for basis in ("baseline", "stress"):
        res = _run(basis)
        assert all(s.error is None for s in res.transcript), basis


def test_subsystem_filter_limits_the_investigation():
    res = _run("stress", subsystems=["FIXED_WING_UAV"])
    # UAV passes even under stress -> no findings, and only UAV was graded
    assert len(res.ctx.findings) == 0
    graded = [s for s in res.transcript if s.tool == "grade_requirements"]
    assert len(graded) == 1
    assert graded[0].arguments["subsystem"] == "FIXED_WING_UAV"
