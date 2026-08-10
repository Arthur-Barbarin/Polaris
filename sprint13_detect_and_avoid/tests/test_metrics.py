import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daa import encounter_set, run_campaign, simulate_encounter
from daa.metrics import SimParams

# A small, fixed campaign used across the metric tests.
ENC = encounter_set(300, seed=13)


def test_baseline_campaign_has_real_collisions():
    r = run_campaign(ENC)
    assert r.nmac_unequipped >= 3          # the encounter set actually stresses the system
    assert r.lowc_unequipped > r.nmac_unequipped


def test_daa_eliminates_nmac_under_perfect_surveillance():
    r = run_campaign(ENC)
    assert r.nmac_equipped == 0
    assert r.risk_ratio == 0.0
    assert r.resolved_nmacs == r.nmac_unequipped
    assert r.unresolved_nmacs == 0


def test_daa_reduces_loss_of_well_clear():
    r = run_campaign(ENC)
    assert r.lowc_rate_equipped < r.lowc_rate_unequipped


def test_alert_lead_is_generous():
    r = run_campaign(ENC)
    assert r.median_alert_lead > 20.0      # tens of seconds of warning


def test_campaign_is_reproducible():
    a = run_campaign(ENC)
    b = run_campaign(ENC)
    assert a.nmac_unequipped == b.nmac_unequipped
    assert a.nmac_equipped == b.nmac_equipped
    assert a.ra_counts == b.ra_counts


def test_encounter_set_is_seed_reproducible():
    e1 = encounter_set(50, seed=99)
    e2 = encounter_set(50, seed=99)
    assert [x.intruder.pos for x in e1] == [x.intruder.pos for x in e2]
    e3 = encounter_set(50, seed=100)
    assert [x.intruder.pos for x in e1] != [x.intruder.pos for x in e3]


def test_degraded_surveillance_reintroduces_risk():
    stress = run_campaign(ENC, sim=SimParams(surveillance_range=926.0))
    assert stress.nmac_equipped >= 1        # late detection -> residual collisions
    assert 0.0 < stress.risk_ratio <= 1.0
    assert stress.unresolved_nmacs >= 1
    assert stress.median_alert_lead < 25.0  # much less warning than nominal


def test_single_encounter_outcome_fields():
    o = simulate_encounter(ENC[0], equipped=True)
    assert o.min_slant >= 0
    assert o.ra_name in {"NONE", "MAINTAIN", "CLIMB", "DESCEND", "TURN_LEFT", "TURN_RIGHT"}
