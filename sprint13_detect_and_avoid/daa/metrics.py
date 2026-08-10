"""Closed-loop encounter simulation and campaign-level safety metrics.

``simulate_encounter`` flies one encounter forward in time. With the DAA
system *disabled* the ownship holds course — this is the baseline hazard. With
it *enabled* the ownship runs the detector each cycle; on the first predicted
loss of Well Clear it selects and commits a resolution advisory and flies it
through the conflict.

``run_campaign`` runs a whole encounter set both ways and rolls the outcomes up
into the numbers that actually matter for a DAA safety case:

    NMAC rate (unequipped vs equipped)   — did we enter the collision volume?
    risk ratio = NMAC_equipped / NMAC_unequipped   — the standard DAA benefit metric
    loss-of-Well-Clear rate               — did we even lose separation assurance?
    alert lead time                       — how many seconds of warning did we get?

A risk ratio well below 1 is the headline: it is exactly how DO-365 / SC-228
quantify the collision-avoidance benefit of an equipage.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median

from .geometry import State, Encounter, time_to_cpa, horizontal_closure_rate
from .wellclear import (
    WellClearParams,
    NMACParams,
    DWC,
    NMAC,
    loss_of_well_clear,
    predicted_lowc,
)
from .resolution import (
    Maneuver,
    ResolutionParams,
    select_ra,
    apply_maneuver,
    MANEUVER_SET,
)

_MAINTAIN = MANEUVER_SET[0]  # the "MAINTAIN" maneuver


@dataclass(frozen=True)
class SimParams:
    """Closed-loop simulation settings."""

    dt: float = 0.5            # s — simulation step
    t_end: float = 150.0       # s — hard stop
    alert_lookahead: float = 45.0   # s — detector prediction horizon
    detect_dt: float = 1.0     # s — detector grid step
    post_cpa_hold: float = 15.0     # s — keep running past CPA to capture min sep
    surveillance_range: float = float("inf")  # m — sensor cannot see intruder beyond this


@dataclass(frozen=True)
class EncounterOutcome:
    """Result of one closed-loop simulation."""

    encounter_id: int
    equipped: bool
    nmac: bool
    lowc: bool
    min_horizontal: float
    min_vertical: float
    min_slant: float
    alerted: bool = False
    alert_time: float = math.inf
    alert_lead: float = math.inf   # seconds of warning before nominal CPA
    ra_name: str = "NONE"


def _straight(s: State, dt: float) -> State:
    return State(s.x + s.vx * dt, s.y + s.vy * dt, s.z + s.vz * dt, s.vx, s.vy, s.vz)


def simulate_encounter(
    enc: Encounter,
    equipped: bool,
    sim: SimParams = SimParams(),
    wc: WellClearParams = DWC,
    nmac: NMACParams = NMAC,
    res: ResolutionParams = ResolutionParams(),
) -> EncounterOutcome:
    """Fly one encounter to resolution and return its outcome."""
    own, intr = enc.ownship, enc.intruder
    t_cpa_nominal = time_to_cpa(own, intr)
    t_stop = min(sim.t_end, t_cpa_nominal + sim.post_cpa_hold)

    ra: Maneuver = _MAINTAIN
    ra_committed = False
    alerted = False
    alert_time = math.inf
    ra_name = "NONE"

    min_h = math.hypot(intr.x - own.x, intr.y - own.y)
    min_v = abs(intr.z - own.z)
    min_slant = math.hypot(min_h, min_v)
    saw_nmac = False
    saw_lowc = False

    t = 0.0
    n_steps = int(round(t_stop / sim.dt)) + 1
    for _ in range(n_steps):
        h = math.hypot(intr.x - own.x, intr.y - own.y)
        v = abs(intr.z - own.z)
        slant = math.hypot(h, v)
        if slant < min_slant:
            min_slant, min_h, min_v = slant, h, v
        if h < nmac.horizontal and v < nmac.vertical:
            saw_nmac = True
        if loss_of_well_clear(own, intr, wc):
            saw_lowc = True

        if equipped and not ra_committed and h <= sim.surveillance_range:
            will, _ = predicted_lowc(own, intr, sim.alert_lookahead, wc, sim.detect_dt)
            if will:
                alerted = True
                alert_time = t
                ra, _pred = select_ra(own, intr, res, wc)
                ra_committed = True
                ra_name = ra.name

        own = apply_maneuver(own, ra, sim.dt) if equipped else _straight(own, sim.dt)
        intr = _straight(intr, sim.dt)
        t += sim.dt
        if t > t_stop:
            break

    alert_lead = (t_cpa_nominal - alert_time) if alerted else math.inf
    return EncounterOutcome(
        encounter_id=enc.encounter_id,
        equipped=equipped,
        nmac=saw_nmac,
        lowc=saw_lowc,
        min_horizontal=min_h,
        min_vertical=min_v,
        min_slant=min_slant,
        alerted=alerted,
        alert_time=alert_time,
        alert_lead=alert_lead,
        ra_name=ra_name,
    )


@dataclass
class CampaignResult:
    """Aggregate safety metrics over an encounter set, both ways."""

    n: int
    nmac_unequipped: int
    nmac_equipped: int
    lowc_unequipped: int
    lowc_equipped: int
    median_alert_lead: float
    min_sep_equipped_p05: float
    resolved_nmacs: int
    unresolved_nmacs: int
    ra_counts: dict[str, int] = field(default_factory=dict)
    outcomes_equipped: list[EncounterOutcome] = field(default_factory=list)
    outcomes_unequipped: list[EncounterOutcome] = field(default_factory=list)

    @property
    def nmac_rate_unequipped(self) -> float:
        return self.nmac_unequipped / self.n if self.n else 0.0

    @property
    def nmac_rate_equipped(self) -> float:
        return self.nmac_equipped / self.n if self.n else 0.0

    @property
    def risk_ratio(self) -> float:
        """NMAC_equipped / NMAC_unequipped — the DAA collision-avoidance benefit."""
        if self.nmac_unequipped == 0:
            return float("nan")
        return self.nmac_equipped / self.nmac_unequipped

    @property
    def lowc_rate_unequipped(self) -> float:
        return self.lowc_unequipped / self.n if self.n else 0.0

    @property
    def lowc_rate_equipped(self) -> float:
        return self.lowc_equipped / self.n if self.n else 0.0


def _percentile(xs: list[float], q: float) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    idx = min(int(q * (len(s) - 1)), len(s) - 1)
    return s[idx]


def run_campaign(
    encounters: list[Encounter],
    sim: SimParams = SimParams(),
    wc: WellClearParams = DWC,
    nmac: NMACParams = NMAC,
    res: ResolutionParams = ResolutionParams(),
) -> CampaignResult:
    """Run every encounter unequipped and equipped; roll up the metrics."""
    un: list[EncounterOutcome] = []
    eq: list[EncounterOutcome] = []
    for enc in encounters:
        un.append(simulate_encounter(enc, False, sim, wc, nmac, res))
        eq.append(simulate_encounter(enc, True, sim, wc, nmac, res))

    n = len(encounters)
    nmac_un = sum(o.nmac for o in un)
    nmac_eq = sum(o.nmac for o in eq)
    lowc_un = sum(o.lowc for o in un)
    lowc_eq = sum(o.lowc for o in eq)

    leads = [o.alert_lead for o in eq if o.alerted and math.isfinite(o.alert_lead)]
    med_lead = median(leads) if leads else float("nan")

    ra_counts: dict[str, int] = {}
    for o in eq:
        ra_counts[o.ra_name] = ra_counts.get(o.ra_name, 0) + 1

    # NMACs in the baseline that the equipped system prevented / failed to prevent.
    resolved = unresolved = 0
    eq_by_id = {o.encounter_id: o for o in eq}
    for o in un:
        if o.nmac:
            if eq_by_id[o.encounter_id].nmac:
                unresolved += 1
            else:
                resolved += 1

    min_sep_p05 = _percentile([o.min_slant for o in eq], 0.05)

    return CampaignResult(
        n=n,
        nmac_unequipped=nmac_un,
        nmac_equipped=nmac_eq,
        lowc_unequipped=lowc_un,
        lowc_equipped=lowc_eq,
        median_alert_lead=med_lead,
        min_sep_equipped_p05=min_sep_p05,
        resolved_nmacs=resolved,
        unresolved_nmacs=unresolved,
        ra_counts=ra_counts,
        outcomes_equipped=eq,
        outcomes_unequipped=un,
    )
