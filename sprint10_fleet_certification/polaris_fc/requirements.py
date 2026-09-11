"""Fleet certification requirements catalog.

Every requirement is a *verifiable* statement — it has an evidence source
(a specific artefact + metric in Sprints 7-9) and a bound with an operator.
No adjectives ("robust", "safe"): all criteria are numeric comparisons
against the metrics that the sprint test-card engines already emit.

Requirements are versioned by CATALOG_VERSION so an exported evidence
package can be traced to the exact acceptance thresholds in force when it
was graded.

Design notes:
  - IDs are stable and hierarchical (FC-<SUBSYSTEM>-<NNN>) so cross-links
    from anomaly-triage clusters to the requirement that opened them stay
    stable across re-runs.
  - `aggregate` says how to fold multiple runs into one number per
    requirement: worst_case, mean, pass_fraction, or exists_pass.
  - `severity` drives the go/no-go rollup at the subsystem level.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List


CATALOG_VERSION = "1.1.0"
# 1.1.0 (2026-09-11): FC-BAT-002 re-expressed from a mean of percentage
#   advantages to a worst-case bound over the conditions that require
#   closed-loop estimation, and FC-BAT-005 split out of it so the one
#   condition where the EKF loses to open-loop counting cannot be averaged
#   away. An exported evidence package tagged 1.0.0 was graded against the
#   old catalogue and is NOT comparable requirement-for-requirement with a
#   1.1.0 package. See integration_campaign_2026-09 finding F2-4.


class Subsystem(str, Enum):
    BATTERY_PACK = "BATTERY_PACK"
    FIXED_WING_UAV = "FIXED_WING_UAV"
    LANDING_MULTIROTOR = "LANDING_MULTIROTOR"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"   # any FAIL blocks certification
    MAJOR = "MAJOR"         # FAIL requires waiver + mitigation
    MINOR = "MINOR"         # FAIL is a finding, not a blocker


@dataclass(frozen=True)
class Requirement:
    id: str
    subsystem: Subsystem
    title: str
    rationale: str            # why this requirement exists (regulatory / physics)
    artefact_role: str        # which artefact (e.g. "campaign", "triage")
    metric: str               # which field to read
    op: str                   # "<=" | ">=" | "==True" | "==False" | "pass_frac>="
    bound: float
    unit: str
    aggregate: str            # "worst_case" | "mean" | "pass_fraction" | "exists_pass"
    scenario_filter: str | None = None   # restrict to one scenario name
    severity: Severity = Severity.MAJOR


# ---- Battery pack (sprint 7) -------------------------------------------------
BATTERY_REQS: List[Requirement] = [
    Requirement(
        id="FC-BAT-001",
        subsystem=Subsystem.BATTERY_PACK,
        title="EKF SOC RMS error under worst characterisation scenario",
        rationale=(
            "State-of-charge accuracy under sensor bias and thermal extremes "
            "is the primary driver of usable range guarantees and low-cell "
            "cut-off logic. EKF must remain <5% RMS across every "
            "characterisation scenario."),
        artefact_role="estimator_benchmark",
        metric="ekf_rms",
        op="<=", bound=0.06, unit="SOC",
        aggregate="worst_case",
        severity=Severity.MAJOR,   # cold-temp EKF is a known degradation
                                   # regime, tracked as a finding rather
                                   # than a certification blocker.
    ),
    Requirement(
        id="FC-BAT-002",
        subsystem=Subsystem.BATTERY_PACK,
        title="EKF advantage where closed-loop estimation is required",
        rationale=(
            "Justifies the added complexity of the EKF vs. a coulomb counter "
            "in the conditions it exists to handle: a wrong initial state of "
            "charge, which open-loop counting can never recover from, and "
            "off-nominal soak temperature. In EVERY such condition the "
            "SOC-RMS reduction must exceed 60%. This requirement "
            "deliberately does not average across the characterisation "
            "matrix. Until 2026-09-11 it did, on a statistic FA-002 rev B "
            "withdrew, and the average hid the behaviour FC-BAT-005 now "
            "states outright. See integration_campaign_2026-09 finding F2-4."),
        artefact_role="estimator_benchmark",
        metric="__ekf_advantage_where_required__",
        op=">=", bound=60.0, unit="%",
        aggregate="worst_case",
        severity=Severity.MAJOR,
    ),
    Requirement(
        id="FC-BAT-003",
        subsystem=Subsystem.BATTERY_PACK,
        title="Failure-mode triage identifies at least one degradation cluster",
        rationale=(
            "The pack must expose a triage bucket labelled with a physical "
            "degradation mode (SEI growth, lithium plating, internal short, "
            "electrolyte depletion) — a purely HEALTHY mapping is a hidden "
            "false negative."),
        artefact_role="triage_model",
        metric="__non_healthy_cluster_count__",
        op=">=", bound=3.0, unit="clusters",
        aggregate="exists_pass",
        severity=Severity.MAJOR,
    ),
    Requirement(
        id="FC-BAT-004",
        subsystem=Subsystem.BATTERY_PACK,
        title="Remaining useful life is finite for every non-healthy mode",
        rationale=(
            "RUL projection must return a bounded number of cycles for each "
            "degradation label. An 'infinite' projection means the "
            "extrapolator failed to fit the fade curve."),
        artefact_role="rul_projections",
        metric="__all_finite_non_healthy__",
        op="==True", bound=1.0, unit="bool",
        aggregate="exists_pass",
        severity=Severity.CRITICAL,
    ),
    Requirement(
        id="FC-BAT-005",
        subsystem=Subsystem.BATTERY_PACK,
        title="EKF must not be worse than open-loop counting in any condition",
        rationale=(
            "A closed-loop estimator beaten by the open-loop counter it "
            "replaces is a net loss in that condition, whatever its average "
            "across the matrix. Split out of FC-BAT-002 on 2026-09-11 so the "
            "condition cannot be averaged away a second time. This "
            "requirement is EXPECTED TO FAIL on the current characterisation: "
            "under a pure current-shunt bias with a correct initial guess the "
            "EKF reaches 0.0575 SOC RMS against the counter's 0.0287, because "
            "its state vector [SOC, v_rc1, v_rc2] carries no current-bias "
            "term and a DC offset is therefore not observable to it. That is "
            "a real deficiency, tracked as a finding rather than hidden. See "
            "FA-002 rev B section 4."),
        artefact_role="estimator_benchmark",
        metric="__ekf_never_worse_than_open_loop__",
        op=">=", bound=0.0, unit="%",
        aggregate="worst_case",
        severity=Severity.MAJOR,
    ),
]


# ---- Fixed-wing UAV (sprint 8) -----------------------------------------------
UAV_REQS: List[Requirement] = [
    Requirement(
        id="FC-UAV-001",
        subsystem=Subsystem.FIXED_WING_UAV,
        title="Nominal mission completes with full test-card compliance",
        rationale=(
            "Baseline demonstration that the closed-loop stack (dynamics + "
            "autopilot + EKF) completes the planned mission without any "
            "test-card violation, before considering fault injection."),
        artefact_role="campaign",
        metric="passed",
        op="pass_frac>=", bound=1.0, unit="frac",
        aggregate="pass_fraction",
        scenario_filter="nominal",
        severity=Severity.CRITICAL,
    ),
    Requirement(
        id="FC-UAV-002",
        subsystem=Subsystem.FIXED_WING_UAV,
        title="Geofence containment across every scenario",
        rationale=(
            "Geofence containment is a Part 89-adjacent safety property: "
            "no injected fault may result in a breach, regardless of "
            "whether the mission completes."),
        artefact_role="campaign",
        metric="geofence_breach",
        op="==False", bound=0.0, unit="bool",
        aggregate="worst_case",
        severity=Severity.CRITICAL,
    ),
    Requirement(
        id="FC-UAV-003",
        subsystem=Subsystem.FIXED_WING_UAV,
        title="Cross-track RMS bound in nominal conditions",
        rationale=(
            "Path-following performance envelope for straight-leg segments; "
            "guarantees a corridor width that Part 108-NPRM lateral-buffer "
            "planning can rely on."),
        artefact_role="campaign",
        metric="cross_track_rms",
        op="<=", bound=5.0, unit="m",
        aggregate="worst_case",
        scenario_filter="nominal",
        severity=Severity.MAJOR,
    ),
    Requirement(
        id="FC-UAV-004",
        subsystem=Subsystem.FIXED_WING_UAV,
        title="Anomaly triage per-class accuracy",
        rationale=(
            "Post-flight triage must correctly bucket each fault family; "
            "operationally this is what tells a fleet manager which "
            "subsystem to inspect first after a returned mission."),
        artefact_role="triage",
        metric="overall_accuracy",
        op=">=", bound=0.85, unit="frac",
        aggregate="exists_pass",
        severity=Severity.MAJOR,
    ),
]


# ---- Landing multirotor (sprint 9) -------------------------------------------
LANDING_REQS: List[Requirement] = [
    Requirement(
        id="FC-LDG-001",
        subsystem=Subsystem.LANDING_MULTIROTOR,
        title="Touchdown lateral error inside pad acceptance radius (nominal)",
        rationale=(
            "Primary landing-accuracy card: on nominal approaches, every "
            "seed must land inside the pad's own acceptance radius."),
        artefact_role="campaign",
        metric="touchdown_lateral",
        op="<=", bound=0.5, unit="m",
        aggregate="worst_case",
        scenario_filter="nominal",
        severity=Severity.CRITICAL,
    ),
    Requirement(
        id="FC-LDG-002",
        subsystem=Subsystem.LANDING_MULTIROTOR,
        title="Sink rate at touchdown (nominal)",
        rationale=(
            "Structural landing-gear load envelope: touchdown sink must "
            "stay below the design impact velocity."),
        artefact_role="campaign",
        metric="touchdown_sink",
        op="<=", bound=1.0, unit="m/s",
        aggregate="worst_case",
        scenario_filter="nominal",
        severity=Severity.CRITICAL,
    ),
    Requirement(
        id="FC-LDG-003",
        subsystem=Subsystem.LANDING_MULTIROTOR,
        title="Unsafe finals must trigger a go-around, not a landing",
        rationale=(
            "Safety of the decision-height abort logic: when vision is "
            "lost or the vehicle is unstable on final, the guidance MUST "
            "reject the landing rather than commit a bad touchdown."),
        artefact_role="campaign",
        metric="__unsafe_becomes_reject__",
        op="==True", bound=1.0, unit="bool",
        aggregate="exists_pass",
        severity=Severity.CRITICAL,
    ),
    Requirement(
        id="FC-LDG-004",
        subsystem=Subsystem.LANDING_MULTIROTOR,
        title="Vision availability on final",
        rationale=(
            "The landing filter depends on high vision availability below "
            "the decision height; a run with <70% availability on final "
            "is graded FAIL by the sprint 9 card engine."),
        artefact_role="campaign",
        metric="vision_avail_final",
        op="pass_frac>=", bound=0.90, unit="frac",
        aggregate="pass_fraction",
        scenario_filter="nominal",
        severity=Severity.MAJOR,
    ),
    Requirement(
        id="FC-LDG-005",
        subsystem=Subsystem.LANDING_MULTIROTOR,
        title="Triage identifies each fault family it saw",
        rationale=(
            "The unsupervised triage over approach logs must correctly "
            "bucket each fault family; a hidden fault-family miss means "
            "post-flight root-cause tooling would leave that failure "
            "unattributed."),
        artefact_role="triage",
        metric="__fault_families_identified__",
        op=">=", bound=8.0, unit="families",
        aggregate="exists_pass",
        severity=Severity.MAJOR,
    ),
]


REQUIREMENTS: List[Requirement] = BATTERY_REQS + UAV_REQS + LANDING_REQS


def load_requirements(subsystem: Subsystem | None = None) -> List[Requirement]:
    if subsystem is None:
        return list(REQUIREMENTS)
    return [r for r in REQUIREMENTS if r.subsystem == subsystem]
