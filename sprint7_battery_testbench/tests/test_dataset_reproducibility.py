"""Regression tests locking the two Phase 1 fixes of the S7 -> S12 integration
campaign (integration_campaign_2026-09).

Both defects were invisible to the existing suite: nothing in this sprint ever
compared the code against its own committed data, and nothing ever checked that
a scenario declaring `guess_err = 0.0` actually got a correct seed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from polaris_bms import Fault                          # noqa: E402
from polaris_bms.cycler import run_cycling_campaign    # noqa: E402
from polaris_bms.triage import rul_projection          # noqa: E402

DATA = REPO / "data"

# (label, fault, severity, temperature_k) exactly as scripts/run_cycling_campaign.py
# configures them. Kept in sync deliberately: if that table changes, the committed
# dataset must be regenerated and this test updated in the same commit.
SCENARIOS = {
    "HEALTHY": (Fault.NONE, 0.0, 298.15),
    "LITHIUM_PLATING": (Fault.LITHIUM_PLATING, 0.8, 283.15),
    "SEI_GROWTH": (Fault.SEI_GROWTH, 0.7, 308.15),
    "INTERNAL_SHORT": (Fault.INTERNAL_SHORT, 0.6, 298.15),
    "ELECTROLYTE_DEPLETION": (Fault.ELECTROLYTE_DEPLETION, 0.9, 313.15),
}

# Every feature the FA-001 tables are built from. soh_pct pins the capacity-fade
# coefficient k_cyc; ir_drop_v and peak_charge_dvdq pin the resistance-growth
# coefficient k_r_cyc. Both had drifted away from their generating values
# (0.0030 and 0.0008) without any test noticing -- finding F1-1.
PINNED = ("soh_pct", "d_soh_pct", "ir_drop_v", "rest_relaxation_v",
          "peak_charge_dvdq", "discharge_capacity_ah", "coulombic_efficiency")


@pytest.fixture(scope="module")
def shipped():
    path = DATA / "cycle_records.json"
    if not path.is_file():
        pytest.skip("data/cycle_records.json not present")
    return json.load(open(path))


@pytest.mark.parametrize("label", sorted(SCENARIOS))
def test_committed_dataset_is_reproducible(shipped, label):
    """The model must still produce the dataset this sprint ships and reports on.

    This is the test that would have caught F1-1: cpp/cell_model.hpp carried
    k_cyc = 0.0090 and k_r_cyc = 0.0020, while data/cycle_records.json had been
    generated with 0.0030 and 0.0008. Every number in FA-001 comes from that
    dataset, so the report described a model that was no longer in the repository.
    """
    fault, sev, T_k = SCENARIOS[label]
    want = [r for r in shipped if r["fault"] == label]
    assert want, f"no {label} records in the committed dataset"

    got = run_cycling_campaign(n_cycles=len(want), fault=fault,
                               fault_severity=sev, temperature_k=T_k)
    assert len(got) == len(want)

    for rec, ref in zip(got, want):
        for key in PINNED:
            assert getattr(rec, key) == pytest.approx(ref[key], rel=1e-9, abs=1e-12), (
                f"{label} cycle {ref['cycle']}: {key} drifted from the committed "
                f"dataset ({getattr(rec, key)!r} vs {ref[key]!r}). Either a model "
                f"coefficient changed without regenerating data/, or data/ is stale."
            )


def test_committed_rul_projections_match():
    """data/rul_projections.json must be what rul_projection() returns today."""
    recs_path = DATA / "cycle_records.json"
    rul_path = DATA / "rul_projections.json"
    if not (recs_path.is_file() and rul_path.is_file()):
        pytest.skip("data/ not present")
    from polaris_bms.cycler import CycleRecord
    recs = json.load(open(recs_path))
    stored = json.load(open(rul_path))
    for label, expected in stored.items():
        rows = [CycleRecord(**r) for r in recs if r["fault"] == label]
        assert rul_projection(rows) == expected, (
            f"{label}: rul_projection now returns "
            f"{rul_projection(rows)}, data/rul_projections.json says {expected}"
        )


def test_seed_guard_does_not_invent_a_guess_error():
    """A scenario declaring no guess error must be seeded with the true SOC.

    This is the test that would have caught F1-5: the guard clipped to
    (0.05, 0.95), so a cell starting at soc0 = 1.0 handed every estimator a seed
    of 0.95 -- a 0.05 error the scenario never asked for, which open-loop coulomb
    counting can never recover from and which inflated the EKF's measured
    advantage. See FA-002 rev B.
    """
    from benchmark_estimators import seed_guess

    # A full cell with no declared guess error must be seeded exactly.
    assert seed_guess(1.0, 0.0) == 1.0
    # An empty cell likewise.
    assert seed_guess(0.0, 0.0) == 0.0
    # A declared guess error must be applied in full, not partially absorbed.
    for true_soc, err in ((1.0, 0.4), (0.8, 0.2), (0.5, 0.05), (1.0, 0.02)):
        assert seed_guess(true_soc, err) == pytest.approx(true_soc - err)
    # The guard still keeps the seed physical.
    assert seed_guess(0.1, 0.5) == 0.0
    assert seed_guess(1.0, -0.5) == 1.0
