"""Polaris Sprint 10 — Fleet Certification Console.

Cross-subsystem traceability layer over the artefacts produced by Sprints 7-9:

  - sprint7_battery_testbench    -> data/{estimator_benchmark,triage_model,rul_projections,cycle_records}.json
  - sprint8_flight_test_harness  -> data/{campaign,triage}.json
  - sprint9_precision_landing    -> data/{campaign,triage}.json

Sprint 10 does not re-run those simulators. It reads their versioned outputs,
maps each verified requirement to a specific measurement in those outputs,
grades the requirement PASS / FAIL, and joins failures to the anomaly-triage
cluster the responsible run landed in.

The point is not another dashboard: it is the traceability matrix a DER /
V&V engineer actually keeps — requirement -> test card -> measurement ->
evidence hash -> anomaly root cause -> exportable evidence package.
"""
from .requirements import (
    REQUIREMENTS, Requirement, Subsystem, Severity, load_requirements,
)
from .evidence import (
    EvidenceItem, RequirementResult, RollupResult,
    build_evidence, rollup, run_summary,
)
from .provenance import evidence_hash, artefact_manifest

__all__ = [
    "REQUIREMENTS", "Requirement", "Subsystem", "Severity", "load_requirements",
    "EvidenceItem", "RequirementResult", "RollupResult",
    "build_evidence", "rollup", "run_summary",
    "evidence_hash", "artefact_manifest",
]

__version__ = "1.0.0"
