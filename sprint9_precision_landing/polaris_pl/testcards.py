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
        return {"scenario": self.scenario, "label": self.label,
                "outcome": self.outcome, "passed": self.passed,
                **self.metrics.as_dict()}


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
        if c.unit.startswith(">="):
            ok = (not np.isnan(val)) and val >= c.bound
        else:
            ok = (not np.isnan(val)) and val <= c.bound
        all_pass = all_pass and ok
        results.append(CardResult(c.name, float(val), c.bound, c.unit, ok))
    return LandingReport(m.scenario, m.label, CARD_VERSION,
                         "PASS" if all_pass else "FAIL", all_pass, results, m)
