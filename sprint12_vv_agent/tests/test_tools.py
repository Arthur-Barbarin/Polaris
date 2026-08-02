"""Tool-layer contract tests: schemas valid, grounding enforced."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from polaris_agent.tools import build_registry, BASES


def test_all_tools_have_valid_json_schema():
    reg = build_registry()
    for spec in reg.specs():
        schema = spec.parameters
        assert schema["type"] == "object"
        assert "properties" in schema
        # every 'required' name must be declared in properties
        for name in schema.get("required", []):
            assert name in schema["properties"], (spec.name, name)
        # anthropic rendering must carry name + input_schema
        a = spec.to_anthropic()
        assert a["name"] == spec.name and "input_schema" in a


def test_registry_rejects_tools_outside_allow_list():
    reg = build_registry()
    with pytest.raises(KeyError):
        reg.call("os_system", {"cmd": "rm -rf /"})


def test_baseline_fleet_is_green():
    reg = build_registry(basis="baseline")
    out = reg.call("list_subsystems", {})
    assert out["fleet_status"] == "GREEN"
    assert out["acceptance_basis"] == "baseline"


def test_stress_basis_surfaces_two_failures():
    reg = build_registry(basis="stress")
    fails = reg.call("get_failing_requirements", {})
    ids = {f["requirement_id"] for f in fails["failing"]}
    assert ids == {"FC-BAT-001", "FC-LDG-001"}
    # the LDG failure is CRITICAL and therefore blocking
    ldg = next(f for f in fails["failing"] if f["requirement_id"] == "FC-LDG-001")
    assert ldg["blocking"] is True
    bat = next(f for f in fails["failing"] if f["requirement_id"] == "FC-BAT-001")
    assert bat["blocking"] is False


def test_measurements_are_basis_invariant():
    """Tightening a bound must NOT change the measured value — only PASS/FAIL."""
    base = build_registry(basis="baseline")
    strs = build_registry(basis="stress")
    b = next(r for r in base.call("grade_requirements",
             {"subsystem": "BATTERY_PACK"})["results"]
             if r["requirement_id"] == "FC-BAT-001")
    s = next(r for r in strs.call("grade_requirements",
             {"subsystem": "BATTERY_PACK"})["results"]
             if r["requirement_id"] == "FC-BAT-001")
    assert b["measured_value"] == s["measured_value"]
    assert b["status"] == "PASS" and s["status"] == "FAIL"


def test_record_finding_rejected_on_passing_requirement():
    reg = build_registry(basis="baseline")
    with pytest.raises(ValueError):
        reg.call("record_finding", {
            "requirement_id": "FC-BAT-001",
            "root_cause": "n/a", "recommendation": "n/a"})


def test_worst_run_is_the_extreme_failing_run():
    reg = build_registry(basis="stress")
    out = reg.call("inspect_anomaly_triage", {"requirement_id": "FC-LDG-001"})
    # <= requirement: worst failing run is the largest value, == the aggregate
    # worst_case, so the reported worst run matches the graded measurement.
    graded = next(r for r in reg.call("grade_requirements",
                  {"subsystem": "LANDING_MULTIROTOR"})["results"]
                  if r["requirement_id"] == "FC-LDG-001")
    assert out["worst_run"]["value"] == pytest.approx(graded["measured_value"])


def test_bases_registry_is_sane():
    assert BASES["baseline"] == {}
    assert set(BASES["stress"]) == {"FC-BAT-001", "FC-LDG-001"}
