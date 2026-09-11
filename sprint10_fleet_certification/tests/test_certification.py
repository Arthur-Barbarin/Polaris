"""Tests for the fleet certification traceability engine.

The tests intentionally hit both real sprint 7-9 artefacts (integration)
and synthetic fixtures (unit), so a regression in either the schema
assumptions OR the rollup logic gets caught.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from polaris_fc import (                        # noqa: E402
    REQUIREMENTS, Subsystem, Severity, build_evidence, run_summary,
)
from polaris_fc.evidence import _op_check       # noqa: E402
from polaris_fc.provenance import evidence_hash # noqa: E402


REPO = HERE.parents[1]   # parents[0]=tests/, parents[1]=Polaris_sprint/


# --- Unit ---------------------------------------------------------------------

def test_op_check_basic():
    assert _op_check(0.4, "<=", 0.5)
    assert not _op_check(0.6, "<=", 0.5)
    assert _op_check(0.7, ">=", 0.5)
    assert not _op_check(float("nan"), "<=", 1.0)
    assert _op_check(True, "==True", 1.0)
    assert _op_check(False, "==False", 0.0)


def test_evidence_hash_reproducible(tmp_path):
    p = tmp_path / "x.json"
    p.write_bytes(b'{"a": 1}')
    h1 = evidence_hash(p)
    h2 = evidence_hash(p)
    assert h1 == h2
    assert len(h1) == 12
    p.write_bytes(b'{"a": 2}')
    assert evidence_hash(p) != h1


def test_missing_artefact_hash():
    assert evidence_hash(Path("/does/not/exist.json")) == "MISSING"


def test_requirements_have_unique_ids():
    ids = [r.id for r in REQUIREMENTS]
    assert len(ids) == len(set(ids)), "requirement IDs must be unique"


def test_every_requirement_carries_rationale():
    for r in REQUIREMENTS:
        assert r.rationale.strip(), f"{r.id} missing rationale"
        assert len(r.rationale) > 40, f"{r.id} rationale too short"


# --- Integration against the real sprint 7-9 artefacts ------------------------

@pytest.fixture(scope="module")
def rollup():
    return build_evidence(REPO)


def test_manifest_lists_all_expected_artefacts(rollup):
    expected = {
        ("BATTERY_PACK", "estimator_benchmark"),
        ("BATTERY_PACK", "triage_model"),
        ("BATTERY_PACK", "rul_projections"),
        ("BATTERY_PACK", "cycle_records"),
        ("FIXED_WING_UAV", "campaign"),
        ("FIXED_WING_UAV", "triage"),
        ("LANDING_MULTIROTOR", "campaign"),
        ("LANDING_MULTIROTOR", "triage"),
    }
    actual = {(r.subsystem, r.role) for r in rollup.manifest}
    assert expected == actual


def test_landing_unsafe_finals_go_around(rollup):
    r = next(x for x in rollup.all_results() if x.requirement.id == "FC-LDG-003")
    # The whole safety pitch of sprint 9 lives or dies on this one.
    assert r.passed, r.note


def test_nominal_touchdown_within_pad(rollup):
    r = next(x for x in rollup.all_results() if x.requirement.id == "FC-LDG-001")
    assert r.passed, f"nominal worst-case touchdown was {r.aggregated_value}"


def test_uav_nominal_passes(rollup):
    r = next(x for x in rollup.all_results() if x.requirement.id == "FC-UAV-001")
    assert r.passed, f"nominal UAV mission pass fraction {r.aggregated_value}"


def test_battery_ekf_advantage_positive(rollup):
    """FC-BAT-002: worst-case advantage where closed-loop estimation is required.

    The bound is read from the requirement rather than repeated here. It used
    to be hard-coded as 60.0 in this file as well, so changing the catalogue
    meant editing two places and nothing enforced that they agreed.
    """
    r = next(x for x in rollup.all_results() if x.requirement.id == "FC-BAT-002")
    v = r.aggregated_value
    assert v is not None and v >= r.requirement.bound, (
        f"worst-case EKF advantage where required was {v}, "
        f"bound {r.requirement.bound}")


def test_battery_ekf_never_worse_is_a_tracked_finding(rollup):
    """FC-BAT-005 is expected to FAIL, and to fail as a non-blocking finding.

    Under a pure current-shunt bias with a correct seed the EKF is worse than
    the coulomb counter it replaces. That is a real deficiency of the
    estimator, not of this console, and the point of splitting it out of
    FC-BAT-002 is that it stays visible instead of being averaged away. If
    this test starts failing because the requirement PASSES, the estimator was
    improved: invert the expectation deliberately, do not delete the test.
    """
    r = next(x for x in rollup.all_results() if x.requirement.id == "FC-BAT-005")
    assert not r.passed, (
        f"FC-BAT-005 now passes (worst {r.aggregated_value}); the estimator "
        "appears to have been fixed, so invert this expectation deliberately")
    assert not r.blocking, "FC-BAT-005 is MAJOR and must not block certification"


def test_summary_shape(rollup):
    s = run_summary(rollup)
    assert set(s.keys()) >= {
        "catalog_version", "fleet_status", "requirements_total",
        "requirements_passed", "blocking_findings",
        "manifest_hashes", "by_subsystem",
    }
    assert s["requirements_total"] == len(REQUIREMENTS)
    assert 0 <= s["requirements_passed"] <= s["requirements_total"]


# --- Fault-injection surface (no actual subprocess in tests) ------------------

def test_available_injections_are_well_formed():
    from polaris_fc.inject import available_injections
    plans = available_injections(REPO)
    assert len(plans) >= 3
    subs = {p.subsystem for p in plans}
    assert subs == set(Subsystem)
    for p in plans:
        assert p.cwd.exists(), f"missing sprint dir {p.cwd}"
        assert p.command[0], "empty command"
        assert p.timeout_s > 0
