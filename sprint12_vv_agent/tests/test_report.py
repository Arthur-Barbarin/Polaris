"""Report tests: the agent cannot inject a number into the report."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from polaris_agent import (
    Agent, DeterministicPolicy, build_registry, render_findings_report,
)
from polaris_agent.tools import Finding


def _result(basis="stress"):
    reg = build_registry(basis=basis)
    agent = Agent(registry=reg, policy=DeterministicPolicy())
    return agent.run("goal")


def test_report_has_required_sections():
    md = render_findings_report(_result("stress"))
    for section in ("# Certification Findings Report", "## Decision:",
                    "## Subsystem roll-up", "## Findings",
                    "## Evidence manifest", "## Agent reasoning transcript"):
        assert section in md


def test_report_decision_matches_status():
    assert "NO-GO" in render_findings_report(_result("stress"))
    assert "Decision: **GO**" in render_findings_report(_result("baseline"))


def test_numbers_come_from_evidence_not_findings():
    """A finding with a bogus number in its text must not change the bound.

    The report binds the measured value / bound from the graded roll-up by
    requirement id, so free-text numbers in a finding never reach the
    quantitative fields.
    """
    res = _result("stress")
    # Corrupt a finding's text with a fake number.
    res.ctx.findings = [Finding(
        requirement_id="FC-LDG-001",
        root_cause="the error is 999 meters",   # lie
        recommendation="ignore")]
    md = render_findings_report(res)
    # the real bound/value are present; the lie is only inside the prose line
    assert "0.03884" in md            # real measured value bound from evidence
    assert "999 meters" in md         # appears only as analyst prose
    # the criterion line uses the grounded value, not 999
    crit = [ln for ln in md.splitlines() if "Criterion:" in ln][0]
    assert "999" not in crit


def test_transcript_is_embedded_and_replayable():
    md = render_findings_report(_result("stress"), include_transcript=True)
    assert "finalize(" in md
    assert md.count("grade_requirements(") >= 3
