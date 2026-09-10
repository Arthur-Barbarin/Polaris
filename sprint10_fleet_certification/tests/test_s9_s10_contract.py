"""Integration test across the Sprint 9 / Sprint 10 boundary.

Every other test in this repository exercises one sprint. This one exercises
the seam between two, which is where the defect it describes lives: neither
sprint's own suite can see it, because each is internally consistent.

THE CONTRACT UNDER TEST
-----------------------
Sprint 9 scores a landing twice, on two different axes:

  card verdict      PASS | FAIL | REJECT | TIMEOUT   -- how the test cards
                    graded the run. FAIL means it landed in a way it should
                    not have; REJECT means the guidance correctly refused to
                    land. This is `LandingReport.outcome`.

  flight outcome    LANDED | GO_AROUND | TIMEOUT     -- what the vehicle
                    physically did. This is `LandingMetrics.outcome`.

Sprint 10 grades airworthiness requirements against Sprint 9's serialised
campaign. FC-LDG-003 ("unsafe finals must trigger a go-around, not a landing")
reads a field named `outcome` from each run.

`LandingReport.summary_row()` writes the card verdict under `outcome` and then
splats `**self.metrics.as_dict()` over it, which carries its own `outcome` key
holding the flight outcome. The splat lands last. The card verdict is
therefore never serialised, and Sprint 10 reads the flight outcome under a key
whose documented meaning is the verdict.

STATUS
------
Phase 2 of integration_campaign_2026-09 reproduces this; the fix is Phase 3.
The three tests that assert the intended contract are marked
`xfail(strict=True)`, so they record the defect without turning the suite red
and, being strict, they FAIL the moment the contract is honoured -- which is
what forces the markers off in Phase 3. Drop the `pytestmark` decorator on
each to see the raw failures; the Phase 2 journal has that output.

The fix must keep BOTH values under distinct keys (`card_verdict` and
`flight_outcome`) and update Sprint 10 to read the right one per requirement.
Renaming Sprint 9's field alone would break FC-LDG-003, which explicitly
compares against "GO_AROUND" today.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
for p in (REPO / "sprint9_precision_landing", REPO / "sprint10_fleet_certification"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from polaris_pl import compute_metrics, grade, simulate           # noqa: E402
from polaris_pl.faults import ALL_SCENARIOS                       # noqa: E402
from polaris_fc.evidence import _handle_special_metric            # noqa: E402
from polaris_fc.requirements import REQUIREMENTS                  # noqa: E402

CARD_VERDICTS = {"PASS", "FAIL", "REJECT", "TIMEOUT"}
FLIGHT_OUTCOMES = {"LANDED", "GO_AROUND", "TIMEOUT"}

DT = 0.05

# One run per verdict class, chosen because they are deterministic at DT and
# cover the case that matters most: a LANDED run whose cards FAILED.
#   (scenario, seed, expected card verdict, expected flight outcome)
CASES = [
    ("nominal", 0, "PASS", "LANDED"),
    ("low_light", 0, "FAIL", "LANDED"),
    ("gust", 0, "REJECT", "GO_AROUND"),
]

XFAIL = pytest.mark.xfail(
    strict=True,
    reason="S9 summary_row() splats metrics.as_dict() over its own 'outcome' key, "
           "overwriting the card verdict with the flight outcome. Reproduced in "
           "integration_campaign_2026-09 phase 2; fix scheduled for phase 3.",
)


def _report(scenario: str, seed: int):
    return grade(compute_metrics(simulate(ALL_SCENARIOS[scenario](), seed=seed, dt=DT)))


# --------------------------------------------------------------------------
# Passes today and after the fix: the invariant that makes the bug silent.
# --------------------------------------------------------------------------

def test_the_two_vocabularies_only_overlap_on_timeout():
    """Card verdicts and flight outcomes are different alphabets.

    They share exactly one token, TIMEOUT, which is why the overwrite is
    invisible on timeout runs and detectable on every other run. If these
    vocabularies ever converge, the tests below stop being able to tell the
    two fields apart and must be rewritten.
    """
    assert CARD_VERDICTS & FLIGHT_OUTCOMES == {"TIMEOUT"}


@pytest.mark.parametrize("scenario,seed,verdict,flight", CASES)
def test_grade_really_does_produce_two_distinct_scores(scenario, seed, verdict, flight):
    """In memory, before serialisation, both values exist and are correct.

    This is what makes the loss a serialisation defect rather than a scoring
    one, and it is why Sprint 9's own suite passes.
    """
    rep = _report(scenario, seed)
    assert rep.outcome == verdict
    assert rep.metrics.outcome == flight
    assert rep.outcome in CARD_VERDICTS
    assert rep.metrics.outcome in FLIGHT_OUTCOMES


# --------------------------------------------------------------------------
# The defect. Strict xfail until phase 3.
# --------------------------------------------------------------------------

@XFAIL
@pytest.mark.parametrize("scenario,seed,verdict,flight", CASES)
def test_card_verdict_survives_serialisation(scenario, seed, verdict, flight):
    """The card verdict must be recoverable from the serialised row.

    Sprint 10 consumes `summary_row()` output, not `LandingReport` objects, so
    anything absent here is invisible to every downstream consumer.
    """
    rep = _report(scenario, seed)
    row = rep.summary_row()

    present = [k for k, v in row.items() if v == rep.outcome]
    assert present, (
        f"{scenario} seed {seed}: card verdict {rep.outcome!r} appears under no "
        f"key of the serialised row. Row carries "
        f"{ {k: v for k, v in row.items() if isinstance(v, str)} }"
    )


@XFAIL
def test_a_landed_failure_is_distinguishable_from_a_landed_pass():
    """The worst consequence, isolated.

    `low_light` seed 0 lands but violates a required card: verdict FAIL.
    `nominal` seed 0 lands cleanly: verdict PASS. Both are flight outcome
    LANDED. On the field Sprint 10 reads they are therefore identical, so a
    landing that should never have happened is indistinguishable from a good
    one. In the shipped artefact this collapses 13 FAIL runs into the same
    bucket as 83 PASS runs.
    """
    good = _report("nominal", 0).summary_row()
    bad = _report("low_light", 0).summary_row()

    assert good["outcome"] != bad["outcome"], (
        "a card FAIL and a card PASS serialise to the same 'outcome' value "
        f"({good['outcome']!r}); the verdict is not recoverable from this field"
    )


@XFAIL
def test_s10_ldg003_grades_on_the_card_verdict():
    """Sprint 10's own evaluator, driven by a real Sprint 9 artefact.

    FC-LDG-003 asks whether unsafe finals were rejected. `REJECT` is the card
    verdict for exactly that. The evidence Sprint 10 records should therefore
    carry the verdict; today it records the flight outcome, because that is
    all Sprint 9 hands it.
    """
    req = next(r for r in REQUIREMENTS if r.id == "FC-LDG-003")
    assert req.metric == "__unsafe_becomes_reject__"

    runs = []
    for scenario in ("gust", "vision_dropout", "nominal"):
        for seed in (0, 1):
            row = _report(scenario, seed).summary_row()
            row["seed"] = seed
            runs.append(row)

    result = _handle_special_metric(req, {"runs": runs})
    assert result is not None, "FC-LDG-003 produced no result at all"
    assert result.evidence, "FC-LDG-003 recorded no evidence items"

    values = {e.value for e in result.evidence}
    assert values <= CARD_VERDICTS, (
        f"FC-LDG-003 graded unsafe finals on {sorted(values)}, which are flight "
        f"outcomes, not card verdicts. The requirement is written about the "
        f"REJECT verdict but is evaluated against the vehicle's physical "
        f"outcome, and passes only because Sprint 9 overwrites one with the other."
    )
