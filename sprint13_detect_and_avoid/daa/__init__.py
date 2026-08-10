"""Detect-and-Avoid Studio — tactical collision avoidance for UAS.

A small, grounded model of the RTCA DO-365 / SC-228 Detect-and-Avoid (DAA)
problem: given a pairwise encounter between an ownship and an intruder,
detect a predicted loss of DAA Well Clear, select a resolution advisory (RA),
and measure the safety benefit over a Monte-Carlo encounter set.

Everything is constant-velocity kinematics with published DO-365 thresholds;
no synthetic "scores", every figure traces to a geometric quantity.
"""
from __future__ import annotations

from .geometry import (
    State,
    Encounter,
    propagate,
    relative_state,
    horizontal_range,
    horizontal_closure_rate,
    modified_tau,
    horizontal_miss_distance,
    time_to_cpa,
    closest_point_of_approach,
)
from .wellclear import (
    WellClearParams,
    DWC,
    NMAC,
    is_nmac,
    loss_of_well_clear,
    predicted_lowc,
    separation_at_cpa,
)
from .resolution import (
    Maneuver,
    MANEUVER_SET,
    ResolutionParams,
    select_ra,
    apply_maneuver,
)
from .encounters import EncounterParams, sample_encounter, encounter_set
from .metrics import (
    EncounterOutcome,
    simulate_encounter,
    run_campaign,
    CampaignResult,
)

__all__ = [
    "State",
    "Encounter",
    "propagate",
    "relative_state",
    "horizontal_range",
    "horizontal_closure_rate",
    "modified_tau",
    "horizontal_miss_distance",
    "time_to_cpa",
    "closest_point_of_approach",
    "WellClearParams",
    "DWC",
    "NMAC",
    "is_nmac",
    "loss_of_well_clear",
    "predicted_lowc",
    "separation_at_cpa",
    "Maneuver",
    "MANEUVER_SET",
    "ResolutionParams",
    "select_ra",
    "apply_maneuver",
    "EncounterParams",
    "sample_encounter",
    "encounter_set",
    "EncounterOutcome",
    "simulate_encounter",
    "run_campaign",
    "CampaignResult",
]
