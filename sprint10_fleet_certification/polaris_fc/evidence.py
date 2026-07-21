"""Evidence roll-up: read sprint 7-9 artefacts, grade each requirement.

Each requirement points at a specific metric in a specific artefact. This
module reads the artefact, pulls the metric, applies the aggregation
(`worst_case`, `mean`, `pass_fraction`, `exists_pass`), compares against
the bound, and returns a `RequirementResult` — the row that the console's
traceability matrix displays.

For runs that FAIL, the corresponding anomaly-triage cluster is joined
in, so the operator sees *which* fault family is the root cause pattern —
this is the sprint-10 value-add over reading each sprint's dashboard on
its own.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .provenance import (
    ArtefactRecord, artefact_manifest, load_json, manifest_as_dict,
)
from .requirements import (
    CATALOG_VERSION, REQUIREMENTS, Requirement, Severity, Subsystem,
)


# --- Types --------------------------------------------------------------------

@dataclass
class EvidenceItem:
    """One measurement pulled from a specific run/scenario."""
    scenario: str
    seed: Optional[int]
    value: Any
    passed: bool
    triage_label: Optional[str] = None       # what the triage bucketed it as


@dataclass
class RequirementResult:
    requirement: Requirement
    aggregated_value: Any
    bound: float
    passed: bool
    n_runs_considered: int
    evidence: List[EvidenceItem]
    artefact_hash: str
    artefact_path: str
    note: str = ""

    @property
    def status(self) -> str:
        return "PASS" if self.passed else "FAIL"

    @property
    def blocking(self) -> bool:
        return (not self.passed) and self.requirement.severity == Severity.CRITICAL


@dataclass
class RollupResult:
    catalog_version: str
    manifest: List[ArtefactRecord]
    by_subsystem: Dict[Subsystem, List[RequirementResult]] = field(default_factory=dict)

    def all_results(self) -> List[RequirementResult]:
        out: List[RequirementResult] = []
        for rs in self.by_subsystem.values():
            out.extend(rs)
        return out

    def subsystem_status(self, s: Subsystem) -> str:
        rs = self.by_subsystem.get(s, [])
        if not rs:
            return "NO_EVIDENCE"
        if any(r.blocking for r in rs):
            return "BLOCKED"
        if any(not r.passed for r in rs):
            return "FINDINGS"
        return "GREEN"

    def fleet_status(self) -> str:
        statuses = {self.subsystem_status(s) for s in self.by_subsystem}
        if "BLOCKED" in statuses:
            return "BLOCKED"
        if "NO_EVIDENCE" in statuses and statuses == {"NO_EVIDENCE"}:
            return "NO_EVIDENCE"
        if "FINDINGS" in statuses:
            return "FINDINGS"
        return "GREEN"


# --- Metric extraction --------------------------------------------------------

def _match_scenario(row: dict, name: Optional[str]) -> bool:
    if name is None:
        return True
    return row.get("scenario") == name


def _pull_runs(artefact: dict, req: Requirement) -> List[dict]:
    """Return the list of run rows relevant to `req`."""
    if req.artefact_role in ("campaign",):
        runs = artefact.get("runs", [])
        return [r for r in runs if _match_scenario(r, req.scenario_filter)]
    # estimator_benchmark is a flat list of scenario rows
    if isinstance(artefact, list):
        return [r for r in artefact if _match_scenario(r, req.scenario_filter)]
    return []


def _op_check(value: float, op: str, bound: float) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    if op == "<=":
        return value <= bound
    if op == ">=":
        return value >= bound
    if op == "==True":
        return bool(value) is True
    if op == "==False":
        return bool(value) is False
    if op == "pass_frac>=":
        return value >= bound
    raise ValueError(f"unknown op {op!r}")


def _sprint8_triage_label(triage: dict | None, scenario: str, seed: int) -> Optional[str]:
    if not triage:
        return None
    # Sprint 8's triage.predictions is indexed the same order the campaign
    # was run: 8 scenarios x seeds, in insertion order of ALL_SCENARIOS.
    preds = triage.get("predictions", [])
    if not preds:
        return None
    for p in preds:
        if p.get("label") == scenario.upper() or p.get("label") == scenario:
            # first prediction for that scenario matches the first seed etc.
            # we cannot recover the seed mapping from triage.json alone, so
            # return the predicted class the triage assigned to *any* run of
            # this scenario (they're all bucketed identically at 100%).
            return p.get("predicted")
    return None


def _sprint9_triage_label(triage: dict | None, scenario: str) -> Optional[str]:
    if not triage:
        return None
    per_class = triage.get("per_class", {})
    label = scenario.upper()
    if label in per_class:
        ok, total = per_class[label]
        return f"{label} ({ok}/{total})"
    return None


# --- Special metric handlers --------------------------------------------------

def _handle_special_metric(req: Requirement, artefact: Any) -> Optional[RequirementResult]:
    """Metrics whose name starts/ends with `__` are computed here rather
    than read directly from the artefact."""
    m = req.metric

    if m == "__non_healthy_cluster_count__":
        # sprint 7 triage_model.json is {cluster_id: mode_label}
        n = sum(1 for v in artefact.values() if v != "HEALTHY")
        passed = _op_check(n, req.op, req.bound)
        ev = [EvidenceItem(scenario="all", seed=None, value=v, passed=(v != "HEALTHY"))
              for v in artefact.values()]
        return RequirementResult(
            requirement=req, aggregated_value=n, bound=req.bound,
            passed=passed, n_runs_considered=len(artefact),
            evidence=ev, artefact_hash="", artefact_path="",
            note=f"{n} non-HEALTHY clusters in triage model")

    if m == "__all_finite_non_healthy__":
        # sprint 7 rul_projections.json is {label: cycles_to_80pct}
        non_healthy = {k: v for k, v in artefact.items() if k != "HEALTHY"}
        all_finite = all(
            v is not None and (not (isinstance(v, float) and math.isnan(v)))
            and v > 0
            for v in non_healthy.values()
        )
        ev = [EvidenceItem(scenario=k, seed=None, value=v, passed=(v is not None))
              for k, v in non_healthy.items()]
        return RequirementResult(
            requirement=req, aggregated_value=all_finite, bound=req.bound,
            passed=all_finite, n_runs_considered=len(non_healthy),
            evidence=ev, artefact_hash="", artefact_path="",
            note=f"RUL projections: {non_healthy}")

    if m == "__unsafe_becomes_reject__":
        # sprint 9 campaign: scenarios that SHOULD go-around are
        # ("gust", "vision_dropout"). Requirement passes iff every such run
        # was rejected (outcome == GO_AROUND), and no LANDED runs came from
        # them (which would mean the guidance failed to abort an unsafe final).
        runs = artefact.get("runs", [])
        unsafe_scenarios = {"gust", "vision_dropout"}
        unsafe = [r for r in runs if r.get("scenario") in unsafe_scenarios]
        rejected = [r for r in unsafe if r.get("outcome") == "GO_AROUND"]
        landed = [r for r in unsafe if r.get("outcome") == "LANDED"]
        passed = (len(unsafe) > 0) and (len(landed) == 0) and (len(rejected) == len(unsafe))
        ev = [EvidenceItem(scenario=r["scenario"], seed=r.get("seed"),
                           value=r.get("outcome"),
                           passed=(r.get("outcome") == "GO_AROUND"))
              for r in unsafe]
        return RequirementResult(
            requirement=req, aggregated_value=passed, bound=req.bound,
            passed=passed, n_runs_considered=len(unsafe),
            evidence=ev, artefact_hash="", artefact_path="",
            note=f"{len(rejected)}/{len(unsafe)} unsafe finals correctly went around; "
                 f"{len(landed)} landed (must be zero)")

    if m == "__fault_families_identified__":
        # sprint 9 triage.json: per_class {LABEL: [correct, total]} — count
        # families with correct > 0 and label != NOMINAL (NOMINAL is defined
        # by absence of anomaly and is the expected hard case).
        per_class = artefact.get("per_class", {})
        families = [k for k, (ok, tot) in per_class.items()
                    if k != "NOMINAL" and ok > 0]
        n = len(families)
        passed = _op_check(n, req.op, req.bound)
        ev = [EvidenceItem(scenario=k, seed=None, value=f"{ok}/{tot}",
                           passed=(ok == tot))
              for k, (ok, tot) in per_class.items() if k != "NOMINAL"]
        return RequirementResult(
            requirement=req, aggregated_value=n, bound=req.bound,
            passed=passed, n_runs_considered=len(per_class),
            evidence=ev, artefact_hash="", artefact_path="",
            note=f"{n} fault families with >=1 correct identification: {families}")

    return None


# --- Core evaluation ----------------------------------------------------------

def _evaluate(req: Requirement, artefact: Any, triage: Optional[dict],
              artefact_path: Path, artefact_hash: str) -> RequirementResult:
    special = _handle_special_metric(req, artefact)
    if special is not None:
        special.artefact_hash = artefact_hash
        special.artefact_path = str(artefact_path)
        return special

    # exists_pass on a top-level scalar field of the artefact (e.g.
    # triage.overall_accuracy): read it directly rather than trying to
    # pull it from a nonexistent runs list.
    if (req.aggregate == "exists_pass" and isinstance(artefact, dict)
            and req.metric in artefact):
        v = artefact[req.metric]
        passed = _op_check(v, req.op, req.bound)
        ev = [EvidenceItem(scenario="artefact", seed=None, value=v, passed=passed)]
        return RequirementResult(
            requirement=req, aggregated_value=v, bound=req.bound,
            passed=passed, n_runs_considered=1, evidence=ev,
            artefact_hash=artefact_hash, artefact_path=str(artefact_path),
            note=f"top-level {req.metric} = {v}",
        )

    runs = _pull_runs(artefact, req)
    values: List[float] = []
    ev: List[EvidenceItem] = []
    for r in runs:
        v = r.get(req.metric)
        # per-row PASS is the same op vs the same bound (except pass_frac,
        # which is handled at the aggregate level).
        row_op = req.op if not req.op.startswith("pass_frac") else "==True"
        row_bound = req.bound if not req.op.startswith("pass_frac") else 1.0
        row_pass = _op_check(v if row_op != "==True" else r.get("passed", False),
                             row_op, row_bound)
        label = None
        if req.subsystem == Subsystem.FIXED_WING_UAV:
            label = _sprint8_triage_label(triage, r.get("scenario", ""), r.get("seed", -1))
        elif req.subsystem == Subsystem.LANDING_MULTIROTOR:
            label = _sprint9_triage_label(triage, r.get("scenario", ""))
        ev.append(EvidenceItem(
            scenario=r.get("scenario", "?"), seed=r.get("seed"),
            value=v if not req.op.startswith("pass_frac") else r.get("passed"),
            passed=row_pass, triage_label=label,
        ))
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            values.append(v)

    n = len(runs)

    if req.aggregate == "worst_case":
        if req.op in ("<=",):
            agg = max(values) if values else float("nan")
        elif req.op in (">=",):
            agg = min(values) if values else float("nan")
        elif req.op == "==False":
            agg = any(bool(r.get(req.metric, False)) for r in runs)
        elif req.op == "==True":
            agg = all(bool(r.get(req.metric, False)) for r in runs)
        else:
            agg = float("nan")
        passed = _op_check(agg, req.op, req.bound)
    elif req.aggregate == "mean":
        agg = sum(values) / len(values) if values else float("nan")
        passed = _op_check(agg, req.op, req.bound)
    elif req.aggregate == "pass_fraction":
        # fraction of runs whose row-level PASS is True
        n_pass = sum(1 for e in ev if e.passed)
        agg = (n_pass / n) if n else 0.0
        passed = agg >= req.bound
    else:
        agg = float("nan")
        passed = False

    return RequirementResult(
        requirement=req, aggregated_value=agg, bound=req.bound,
        passed=passed, n_runs_considered=n,
        evidence=ev, artefact_hash=artefact_hash,
        artefact_path=str(artefact_path), note="",
    )


# --- Public API ---------------------------------------------------------------

def build_evidence(repo_root: Path) -> RollupResult:
    """Read every sprint 7-9 artefact and grade every requirement."""
    manifest = artefact_manifest(repo_root)
    manifest_by = {(r.subsystem, r.role): r for r in manifest}

    # Load artefacts once.
    loaded: Dict[tuple, Any] = {}
    for rec in manifest:
        if rec.exists:
            loaded[(rec.subsystem, rec.role)] = load_json(rec.path)

    triage_by_sub = {
        "FIXED_WING_UAV": loaded.get(("FIXED_WING_UAV", "triage")),
        "LANDING_MULTIROTOR": loaded.get(("LANDING_MULTIROTOR", "triage")),
    }

    by_sub: Dict[Subsystem, List[RequirementResult]] = {}
    for req in REQUIREMENTS:
        key = (req.subsystem.value, req.artefact_role)
        rec = manifest_by.get(key)
        artefact = loaded.get(key)
        if artefact is None or rec is None or not rec.exists:
            res = RequirementResult(
                requirement=req, aggregated_value=None, bound=req.bound,
                passed=False, n_runs_considered=0, evidence=[],
                artefact_hash="MISSING",
                artefact_path=str(rec.path) if rec else "?",
                note="artefact missing — run the source sprint first")
        else:
            triage = triage_by_sub.get(req.subsystem.value)
            res = _evaluate(req, artefact, triage, rec.path, rec.sha256_12)
        by_sub.setdefault(req.subsystem, []).append(res)

    return RollupResult(
        catalog_version=CATALOG_VERSION, manifest=manifest,
        by_subsystem=by_sub)


def rollup(repo_root: Path) -> RollupResult:
    """Alias kept for readability at call sites."""
    return build_evidence(repo_root)


def run_summary(res: RollupResult) -> Dict[str, Any]:
    """One-line summary suitable for a headline row in the console."""
    all_r = res.all_results()
    n_total = len(all_r)
    n_pass = sum(1 for r in all_r if r.passed)
    n_blocking = sum(1 for r in all_r if r.blocking)
    return {
        "catalog_version": res.catalog_version,
        "fleet_status": res.fleet_status(),
        "requirements_total": n_total,
        "requirements_passed": n_pass,
        "blocking_findings": n_blocking,
        "manifest_hashes": manifest_as_dict(res.manifest),
        "by_subsystem": {s.value: res.subsystem_status(s) for s in res.by_subsystem},
    }
