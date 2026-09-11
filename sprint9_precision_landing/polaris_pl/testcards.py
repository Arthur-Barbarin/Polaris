"""Landing acceptance metrics + versioned pass/fail test cards.

Outcomes are three-way, the way a flight-test engineer scores a landing test
point:

  PASS    landed within every touchdown / approach tolerance.
  FAIL    landed, but a required card was violated (a landing that should not
          have happened that way — e.g. a hard or off-pad touchdown).
  REJECT  a go-around: the guidance correctly refused to land (vision lost or
          not aligned below the decision height). A safe abort, not a failure
          of the landing cards; validated separately (must climb clear).

`grade()` returns the outcome plus the per-card breakdown for landed runs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from .simulator import ApproachLog, FINAL_APPROACH_Z

CARD_VERSION = "1.0.0"


@dataclass
class LandingMetrics:
    scenario: str
    label: str
    outcome: str
    landed: bool
    go_around: bool
    touchdown_lateral: float
    touchdown_sink: float
    max_lateral_final: float
    vision_avail_final: float
    nav_err_final: float
    max_sink: float
    descent_time: float
    gps_vision_disagree: float
    vision_avail_high: float
    touchdown_radius: float

    def as_dict(self) -> dict:
        return {k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                for k, v in self.__dict__.items()}


def compute_metrics(log: ApproachLog) -> LandingMetrics:
    padx, pady = log.pad_xy
    final = log.z <= FINAL_APPROACH_Z
    if np.any(final):
        max_lat_final = float(np.max(log.lateral_true[final]))
        nav_err = float(np.mean(np.hypot(
            log.est_x[final] - (log.x[final] - padx),
            log.est_y[final] - (log.y[final] - pady))))
    else:
        max_lat_final = float(np.max(log.lateral_true))
        nav_err = float("nan")

    return LandingMetrics(
        scenario=log.scenario, label=log.label, outcome=log.outcome,
        landed=(log.outcome == "LANDED"),
        go_around=(log.outcome == "GO_AROUND"),
        touchdown_lateral=log.touchdown_lateral,
        touchdown_sink=log.touchdown_sink,
        max_lateral_final=max_lat_final,
        vision_avail_final=log.vision_avail_final,
        nav_err_final=nav_err,
        max_sink=float(np.max(log.sink)),
        descent_time=float(log.t[-1]),
        gps_vision_disagree=float(log.gps_vision_disagree),
        vision_avail_high=float(log.vision_avail_high),
        touchdown_radius=float(log.touchdown_radius),
    )


@dataclass
class Criterion:
    name: str
    metric: str
    bound: float
    unit: str


DEFAULT_CRITERIA: List[Criterion] = [
    Criterion("Touchdown lateral error", "touchdown_lateral", 0.5, "m"),
    Criterion("Touchdown sink rate", "touchdown_sink", 1.0, "m/s"),
    Criterion("Max lateral on final", "max_lateral_final", 2.0, "m"),
    Criterion("Vision availability on final", "vision_avail_final", 0.70, ">= frac"),
    Criterion("Nav error on final", "nav_err_final", 0.30, "m"),
]


@dataclass
class CardResult:
    name: str
    value: float
    bound: float
    unit: str
    passed: bool


@dataclass
class LandingReport:
    scenario: str
    label: str
    version: str
    outcome: str          # PASS | FAIL | REJECT | TIMEOUT
    passed: bool          # True only if landed within all tolerances
    results: List[CardResult]
    metrics: LandingMetrics

    def summary_row(self) -> dict:
        """Serialise one graded run for downstream consumers.

        Two different scores are called `outcome` in this module:

          self.outcome          card verdict   PASS | FAIL | REJECT | TIMEOUT
          self.metrics.outcome  flight outcome LANDED | GO_AROUND | TIMEOUT

        Until 2026-09-11 this method wrote the card verdict under "outcome"
        and then splatted `**self.metrics.as_dict()` over it. The splat landed
        last, so the verdict was overwritten by the flight outcome on every
        run and never reached any consumer: Sprint 10 graded FC-LDG-003 on the
        field that displaced it, and Sprint 9's own dashboard rendered its
        PASS/FAIL/REJECT matrix as zeros.

        Both values are now serialised under names that say which is which,
        and the bare "outcome" key is deliberately gone, so no consumer can
        read one while meaning the other. Consumers that need the verdict read
        `card_verdict`; consumers that need what the vehicle physically did
        read `flight_outcome`, or the `landed` / `go_around` booleans beside it.

        See integration_campaign_2026-09, findings F2-1 to F2-3.
        """
        row = dict(self.metrics.as_dict())
        row["flight_outcome"] = row.pop("outcome")
        row["card_verdict"] = self.outcome
        row["scenario"] = self.scenario
        row["label"] = self.label
        row["passed"] = self.passed
        return row


def grade(m: LandingMetrics, criteria: List[Criterion] | None = None) -> LandingReport:
    criteria = criteria or DEFAULT_CRITERIA

    if m.outcome == "GO_AROUND":
        return LandingReport(m.scenario, m.label, CARD_VERSION, "REJECT",
                             False, [], m)
    if m.outcome == "TIMEOUT":
        return LandingReport(m.scenario, m.label, CARD_VERSION, "TIMEOUT",
                             False, [], m)

    results: List[CardResult] = []
    all_pass = True
    for c in criteria:
        val = getattr(m, c.metric)
        # The touchdown-accuracy card uses the pad's own acceptance radius, so
        # a bigger/smaller pad changes what counts as a good landing.
        bound = m.touchdown_radius if c.metric == "touchdown_lateral" else c.bound
        if c.unit.startswith(">="):
            ok = (not np.isnan(val)) and val >= bound
        else:
            ok = (not np.isnan(val)) and val <= bound
        all_pass = all_pass and ok
        results.append(CardResult(c.name, float(val), bound, c.unit, ok))
    return LandingReport(m.scenario, m.label, CARD_VERSION,
                         "PASS" if all_pass else "FAIL", all_pass, results, m)
