"""Tool registry — the *only* way the agent can touch the evidence.

Each tool is a typed, JSON-schema-described function (the exact shape an
LLM function-calling / tool-use API expects). Every tool is deterministic
and grounded: it reads the Sprint 7-11 artefacts through Sprint 10's
`polaris_fc` grading layer and returns structured data. No tool invents a
number, and there is deliberately no "compute arbitrary expression" tool —
the agent's action space is closed over exactly these operations.

Acceptance basis
----------------
The *measurements* are always the real Sprint 7-11 numbers. What can change
is the **acceptance basis** — the set of thresholds a requirement is graded
against. `baseline` is Sprint 10's ratified catalog (the whole fleet passes).
`stress` is a deliberately tightened certification basis used to demonstrate
the analyst's findings path: same real evidence, stricter bounds, so genuine
FAILs appear and the agent must diagnose them. The report always states which
basis is in force; a tightened basis is a hypothetical, not a claim that the
hardware failed.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# --- Locate Sprint 10's grading layer ----------------------------------------

def _find_repo_root(start: Path) -> Path:
    """Walk up until we find the Polaris_sprint root (holds sprint10_*)."""
    p = start.resolve()
    for cand in [p, *p.parents]:
        if (cand / "sprint10_fleet_certification").is_dir():
            return cand
    return start.resolve().parents[2]


REPO_ROOT = _find_repo_root(Path(__file__))
_S10 = REPO_ROOT / "sprint10_fleet_certification"
if str(_S10) not in sys.path:
    sys.path.insert(0, str(_S10))

from polaris_fc import (                                   # noqa: E402
    build_evidence, run_summary, RollupResult, RequirementResult,
)
from polaris_fc.requirements import Subsystem, Severity     # noqa: E402
from polaris_fc.evidence import _op_check                   # noqa: E402
from polaris_fc.inject import available_injections          # noqa: E402


# --- Acceptance bases ---------------------------------------------------------
# A basis maps requirement_id -> tightened bound. Only bounds move; ops,
# metrics and severities are unchanged. Measurements are always real.

BASES: Dict[str, Dict[str, float]] = {
    "baseline": {},
    # A stricter certification basis for demonstration:
    #  - FC-BAT-001: EKF SOC-RMS worst case must be <=0.05 (was 0.06). The
    #    real cold-temperature run measures ~0.0546, so this FAILs (MAJOR).
    #  - FC-LDG-001: nominal touchdown must land inside a 0.03 m pad radius
    #    (was 0.5). Real worst-case is ~0.0388 m, so this FAILs (CRITICAL ->
    #    blocking -> NO-GO), exercising the blocker path.
    "stress": {"FC-BAT-001": 0.05, "FC-LDG-001": 0.03},
}


# --- Tool specification -------------------------------------------------------

@dataclass(frozen=True)
class ToolSpec:
    """A callable tool plus the JSON schema an LLM needs to call it."""
    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable[..., Dict[str, Any]]

    def to_anthropic(self) -> Dict[str, Any]:
        return {"name": self.name, "description": self.description,
                "input_schema": self.parameters}


@dataclass
class Finding:
    requirement_id: str
    root_cause: str
    recommendation: str
    disposition: str = "FINDING"        # FINDING | WAIVER_CANDIDATE | BLOCKER


@dataclass
class ToolContext:
    """Shared, mutable state threaded through every tool call."""
    repo_root: Path = REPO_ROOT
    basis: str = "baseline"
    _rollup: Optional[RollupResult] = None
    findings: List[Finding] = field(default_factory=list)
    finalized: bool = False
    decision_rationale: str = ""
    tool_calls: int = 0

    # -- grading, made basis-aware ------------------------------------------
    def overrides(self) -> Dict[str, float]:
        return BASES.get(self.basis, {})

    def rollup(self) -> RollupResult:
        if self._rollup is None:
            self._rollup = build_evidence(self.repo_root)
        return self._rollup

    def result_for(self, req_id: str) -> Optional[RequirementResult]:
        for r in self.rollup().all_results():
            if r.requirement.id == req_id:
                return r
        return None

    def effective_bound(self, r: RequirementResult) -> float:
        return self.overrides().get(r.requirement.id, r.bound)

    def is_pass(self, r: RequirementResult) -> bool:
        rid = r.requirement.id
        if rid not in self.overrides():
            return r.passed
        return _op_check(r.aggregated_value, r.requirement.op,
                         self.overrides()[rid])

    def is_blocking(self, r: RequirementResult) -> bool:
        return (not self.is_pass(r)) and \
            r.requirement.severity == Severity.CRITICAL

    def run_pass(self, r: RequirementResult, ev) -> bool:
        """Per-run pass under the effective bound (override-aware)."""
        return _op_check(ev.value, r.requirement.op, self.effective_bound(r))

    def worst_run(self, r: RequirementResult):
        """The most extreme *failing* run under the effective bound.

        For a `<=` requirement the worst failing run is the largest value;
        for `>=` it is the smallest. Falls back to the first failing run for
        boolean/other operators. Returns None if nothing fails.
        """
        failing = [ev for ev in r.evidence
                   if ev.value is not None and not self.run_pass(r, ev)]
        if not failing:
            return None
        op = r.requirement.op
        if op == "<=":
            return max(failing, key=lambda e: e.value)
        if op in (">=", "pass_frac>="):
            return min(failing, key=lambda e: e.value)
        return failing[0]

    def subsystem_results(self, sub: Subsystem) -> List[RequirementResult]:
        return self.rollup().by_subsystem.get(sub, [])

    def subsystem_status(self, sub: Subsystem) -> str:
        rs = self.subsystem_results(sub)
        if not rs:
            return "NO_EVIDENCE"
        if any(self.is_blocking(r) for r in rs):
            return "BLOCKED"
        if any(not self.is_pass(r) for r in rs):
            return "FINDINGS"
        return "GREEN"

    def fleet_status(self) -> str:
        statuses = {self.subsystem_status(s) for s in self.rollup().by_subsystem}
        if "BLOCKED" in statuses:
            return "BLOCKED"
        if statuses == {"NO_EVIDENCE"}:
            return "NO_EVIDENCE"
        if "FINDINGS" in statuses:
            return "FINDINGS"
        return "GREEN"

    def failing(self, sub: Optional[Subsystem] = None) -> List[RequirementResult]:
        rs = (self.subsystem_results(sub) if sub
              else self.rollup().all_results())
        return [r for r in rs if not self.is_pass(r)]

    def _rel_artefact(self, r: RequirementResult) -> str:
        try:
            return str(Path(r.artefact_path).resolve()
                       .relative_to(self.repo_root.resolve()))
        except (ValueError, TypeError):
            return r.artefact_path

    def view(self, r: RequirementResult) -> Dict[str, Any]:
        passed = self.is_pass(r)
        return {
            "requirement_id": r.requirement.id,
            "subsystem": r.requirement.subsystem.value,
            "title": r.requirement.title,
            "status": "PASS" if passed else "FAIL",
            "severity": r.requirement.severity.value,
            "blocking": self.is_blocking(r),
            "measured_value": r.aggregated_value,
            "operator": r.requirement.op,
            "bound": self.effective_bound(r),
            "catalog_bound": r.bound,
            "unit": r.requirement.unit,
            "n_runs": r.n_runs_considered,
            "artefact": self._rel_artefact(r),
            "evidence_hash": r.artefact_hash,
            "note": r.note,
        }


def _subsystem(name: str) -> Subsystem:
    try:
        return Subsystem(name)
    except ValueError as e:
        valid = ", ".join(s.value for s in Subsystem)
        raise ValueError(f"unknown subsystem '{name}'. valid: {valid}") from e


# --- Tool implementations -----------------------------------------------------

def _make_tools(ctx: ToolContext) -> List[ToolSpec]:

    def list_subsystems() -> Dict[str, Any]:
        return {
            "acceptance_basis": ctx.basis,
            "fleet_status": ctx.fleet_status(),
            "subsystems": [
                {"subsystem": s.value, "status": ctx.subsystem_status(s)}
                for s in ctx.rollup().by_subsystem
            ],
        }

    def list_requirements(subsystem: str) -> Dict[str, Any]:
        sub = _subsystem(subsystem)
        return {
            "subsystem": sub.value,
            "requirements": [
                {"requirement_id": r.requirement.id, "title": r.requirement.title,
                 "severity": r.requirement.severity.value,
                 "rationale": r.requirement.rationale}
                for r in ctx.subsystem_results(sub)
            ],
        }

    def grade_requirements(subsystem: str) -> Dict[str, Any]:
        sub = _subsystem(subsystem)
        rows = [ctx.view(r) for r in ctx.subsystem_results(sub)]
        return {
            "subsystem": sub.value,
            "acceptance_basis": ctx.basis,
            "subsystem_status": ctx.subsystem_status(sub),
            "n_pass": sum(1 for x in rows if x["status"] == "PASS"),
            "n_fail": sum(1 for x in rows if x["status"] == "FAIL"),
            "results": rows,
        }

    def get_failing_requirements(subsystem: Optional[str] = None) -> Dict[str, Any]:
        sub = _subsystem(subsystem) if subsystem else None
        fails = [ctx.view(r) for r in ctx.failing(sub)]
        return {"acceptance_basis": ctx.basis,
                "n_failing": len(fails), "failing": fails}

    def inspect_anomaly_triage(requirement_id: str) -> Dict[str, Any]:
        r = ctx.result_for(requirement_id)
        if r is None:
            raise ValueError(f"no such requirement: {requirement_id}")
        clusters: Dict[str, int] = {}
        for ev in r.evidence:
            if ev.triage_label:
                clusters[ev.triage_label] = clusters.get(ev.triage_label, 0) + 1
        worst = ctx.worst_run(r)
        return {
            "requirement_id": requirement_id,
            "status": ctx.view(r)["status"],
            "triage_clusters": clusters or {"(none joined)": 0},
            "worst_run": (
                {"scenario": worst.scenario, "seed": worst.seed,
                 "value": worst.value, "triage_label": worst.triage_label}
                if worst else None
            ),
        }

    def get_evidence_provenance(requirement_id: str) -> Dict[str, Any]:
        r = ctx.result_for(requirement_id)
        if r is None:
            raise ValueError(f"no such requirement: {requirement_id}")
        return {
            "requirement_id": requirement_id,
            "artefact_path": ctx._rel_artefact(r),
            "evidence_hash": r.artefact_hash,
            "catalog_version": ctx.rollup().catalog_version,
            "acceptance_basis": ctx.basis,
            "n_runs_considered": r.n_runs_considered,
        }

    def list_fault_injections() -> Dict[str, Any]:
        plans = available_injections(ctx.repo_root)
        return {"injections": [
            {"subsystem": p.subsystem.value, "scenario": p.scenario,
             "label": p.label} for p in plans]}

    def record_finding(requirement_id: str, root_cause: str,
                       recommendation: str,
                       disposition: str = "FINDING") -> Dict[str, Any]:
        r = ctx.result_for(requirement_id)
        if r is None:
            raise ValueError(f"no such requirement: {requirement_id}")
        if ctx.is_pass(r):
            raise ValueError(
                f"{requirement_id} PASSED under basis '{ctx.basis}' — cannot "
                f"record a finding against passing evidence")
        if disposition not in ("FINDING", "WAIVER_CANDIDATE", "BLOCKER"):
            raise ValueError(f"bad disposition: {disposition}")
        ctx.findings = [f for f in ctx.findings
                        if f.requirement_id != requirement_id]
        ctx.findings.append(Finding(
            requirement_id=requirement_id, root_cause=root_cause.strip(),
            recommendation=recommendation.strip(), disposition=disposition))
        return {"recorded": requirement_id, "n_findings": len(ctx.findings)}

    def finalize(decision_rationale: str) -> Dict[str, Any]:
        ctx.finalized = True
        ctx.decision_rationale = decision_rationale.strip()
        return {"finalized": True, "n_findings": len(ctx.findings),
                "fleet_status": ctx.fleet_status()}

    S = [s.value for s in Subsystem]
    return [
        ToolSpec("list_subsystems",
                 "List the subsystems under certification and their current "
                 "roll-up status (GREEN / FINDINGS / BLOCKED) under the active "
                 "acceptance basis. Start here.",
                 {"type": "object", "properties": {}, "required": []},
                 lambda **kw: list_subsystems()),
        ToolSpec("list_requirements",
                 "List the verifiable requirements for one subsystem, with "
                 "severity and rationale (no grades).",
                 {"type": "object",
                  "properties": {"subsystem": {"type": "string", "enum": S}},
                  "required": ["subsystem"]},
                 lambda **kw: list_requirements(**kw)),
        ToolSpec("grade_requirements",
                 "Grade every requirement for one subsystem against the Sprint "
                 "7-11 evidence under the active acceptance basis. Returns "
                 "measured value, bound, operator and PASS/FAIL per requirement.",
                 {"type": "object",
                  "properties": {"subsystem": {"type": "string", "enum": S}},
                  "required": ["subsystem"]},
                 lambda **kw: grade_requirements(**kw)),
        ToolSpec("get_failing_requirements",
                 "Return only the FAILING requirements, optionally filtered to "
                 "one subsystem, with their grounded measurements.",
                 {"type": "object",
                  "properties": {"subsystem": {"type": "string", "enum": S}},
                  "required": []},
                 lambda **kw: get_failing_requirements(**kw)),
        ToolSpec("inspect_anomaly_triage",
                 "For one requirement, return the anomaly-triage cluster(s) and "
                 "the worst run under the active basis — the root-cause pattern "
                 "behind a FAIL.",
                 {"type": "object",
                  "properties": {"requirement_id": {"type": "string",
                                 "description": "e.g. FC-BAT-001"}},
                  "required": ["requirement_id"]},
                 lambda **kw: inspect_anomaly_triage(**kw)),
        ToolSpec("get_evidence_provenance",
                 "Return the artefact path, content hash and catalog version "
                 "backing a requirement's grade — the audit trail.",
                 {"type": "object",
                  "properties": {"requirement_id": {"type": "string"}},
                  "required": ["requirement_id"]},
                 lambda **kw: get_evidence_provenance(**kw)),
        ToolSpec("list_fault_injections",
                 "List the re-runnable campaigns available per subsystem "
                 "(metadata only — does not execute anything).",
                 {"type": "object", "properties": {}, "required": []},
                 lambda **kw: list_fault_injections()),
        ToolSpec("record_finding",
                 "Record an analyst disposition against a FAILING requirement: "
                 "a root-cause hypothesis and a recommendation. Rejected if the "
                 "requirement passed. Do not put numbers here — they are bound "
                 "automatically from the evidence.",
                 {"type": "object",
                  "properties": {
                      "requirement_id": {"type": "string"},
                      "root_cause": {"type": "string",
                          "description": "Concise physical/technical root cause."},
                      "recommendation": {"type": "string",
                          "description": "What to do: waiver, mitigation, re-test."},
                      "disposition": {"type": "string",
                          "enum": ["FINDING", "WAIVER_CANDIDATE", "BLOCKER"]}},
                  "required": ["requirement_id", "root_cause", "recommendation"]},
                 lambda **kw: record_finding(**kw)),
        ToolSpec("finalize",
                 "Close the investigation with a one-paragraph go/no-go "
                 "rationale. Call exactly once, after all failing requirements "
                 "have a recorded finding.",
                 {"type": "object",
                  "properties": {"decision_rationale": {"type": "string"}},
                  "required": ["decision_rationale"]},
                 lambda **kw: finalize(**kw)),
    ]


class ToolRegistry:
    """Name -> ToolSpec, with a guarded dispatch that counts calls."""

    def __init__(self, ctx: ToolContext, specs: List[ToolSpec]):
        self.ctx = ctx
        self._by_name: Dict[str, ToolSpec] = {s.name: s for s in specs}

    def __contains__(self, name: str) -> bool:
        return name in self._by_name

    def names(self) -> List[str]:
        return list(self._by_name)

    def specs(self) -> List[ToolSpec]:
        return list(self._by_name.values())

    def anthropic_schema(self) -> List[Dict[str, Any]]:
        return [s.to_anthropic() for s in self._by_name.values()]

    def call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self._by_name:
            raise KeyError(
                f"tool '{name}' is not in the allow-list: {self.names()}")
        self.ctx.tool_calls += 1
        return self._by_name[name].func(**(arguments or {}))


def build_registry(repo_root: Optional[Path] = None,
                   basis: str = "baseline") -> ToolRegistry:
    if basis not in BASES:
        raise ValueError(f"unknown basis '{basis}'. valid: {list(BASES)}")
    ctx = ToolContext(repo_root=repo_root or REPO_ROOT, basis=basis)
    return ToolRegistry(ctx, _make_tools(ctx))
