"""Flight-test card engine: derive metrics from a log, grade pass/fail.

A "test card" is a named set of quantitative acceptance criteria — the same
concept a flight-test engineer uses to decide whether a test point passed.
Each metric is compared against a bound and tagged PASS / FAIL; the run passes
only if every required card passes.

Criteria are VERSIONED (CARD_VERSION) so a campaign result can be traced to the
exact acceptance thresholds in force when it was graded.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from .simulator import FlightLog

CARD_VERSION = "1.0.0"


@dataclass
class FlightMetrics:
    scenario: str
    label: str
    duration_s: float
    mission_complete: bool
    cross_track_rms: float
    cross_track_max: float
    alt_hold_rms: float
    airspeed_hold_rms: float
    airspeed_mean_err: float
    throttle_sat_pct: float
    bank_sat_pct: float
    est_pos_rmse: float
    est_pos_max: float
    geofence_breach: bool
    settling_time_s: float          # NaN if not measurable / never settled

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        for k, v in d.items():
            if isinstance(v, (np.floating,)):
                d[k] = float(v)
        return d


def _steady_mask(log: FlightLog, warmup_s: float = 10.0,
                 transition_s: float = 10.0) -> np.ndarray:
    """Boolean mask selecting straight-leg, steady-state samples.

    Excludes (a) an initial launch/settle window and (b) a turn-transition
    window after each waypoint switch. Tracking-error acceptance criteria are
    evaluated on straight segments only — standard flight-test practice, since
    a fixed-wing physically cannot corner inside its turn radius while
    following straight-line legs.
    """
    t = log.t
    mask = t >= warmup_s
    switches = np.where(np.diff(log.leg_idx) != 0)[0]
    for idx in switches:
        t_sw = t[idx]
        mask &= ~((t >= t_sw) & (t < t_sw + transition_s))
    if not np.any(mask):          # degenerate: keep everything
        mask = np.ones_like(t, dtype=bool)
    return mask


def compute_metrics(log: FlightLog, settle_band_m: float = 25.0,
                    Va_cmd: float | None = None) -> FlightMetrics:
    af = log.airframe
    Va_cmd = af.Va_cruise if Va_cmd is None else Va_cmd

    steady = _steady_mask(log)
    abs_xt = np.abs(log.e_xt[steady])
    alt_err = (log.h - log.h_cmd)[steady]
    va_err = (log.Va - Va_cmd)[steady]

    bank_sat = np.mean(np.abs(log.phi_c) >= 0.98 * af.phi_max) * 100.0
    thr_sat = np.mean((log.throttle <= 1e-3) | (log.throttle >= 1 - 1e-3)) * 100.0

    from .mission import default_mission  # geofence source
    fence = default_mission().geofence
    breach = bool(np.any([
        not fence.contains(n, e, h)
        for n, e, h in zip(log.pn, log.pe, log.h)
    ]))

    settling = _settling_time(log, settle_band_m, steady)

    return FlightMetrics(
        scenario=log.scenario,
        label=log.label,
        duration_s=float(log.t[-1]),
        mission_complete=log.mission_complete,
        cross_track_rms=float(np.sqrt(np.mean(log.e_xt[steady] ** 2))),
        cross_track_max=float(np.max(abs_xt)),
        alt_hold_rms=float(np.sqrt(np.mean(alt_err ** 2))),
        airspeed_hold_rms=float(np.sqrt(np.mean(va_err ** 2))),
        airspeed_mean_err=float(np.mean(va_err)),
        throttle_sat_pct=float(thr_sat),
        bank_sat_pct=float(bank_sat),
        est_pos_rmse=float(np.sqrt(np.mean(log.est_pos_err ** 2))),
        est_pos_max=float(np.max(log.est_pos_err)),
        geofence_breach=breach,
        settling_time_s=settling,
    )


def _settling_time(log: FlightLog, band_m: float, steady: np.ndarray,
                   window_s: float = 60.0) -> float:
    """Cross-track recovery time attributable to the injected disturbance.

    Measured strictly inside a fixed window [t_onset, t_onset + window_s] and
    on straight-leg samples only, so it reflects the *disturbance response* and
    is not contaminated by unrelated turn-transition excursions later in the
    flight. Returns:
        NaN  if the scenario has no discrete disturbance onset (persistent
             faults set disturbance_t=None) -> settling time is not applicable;
        0.0  if cross-track never leaves the band within the window;
        NaN  if it is still out of band at the end of the window (did not
             settle in time);
        else the time from onset back to the band.
    """
    if log.disturbance_t is None:
        return float("nan")
    t0 = log.disturbance_t
    mask = (log.t >= t0) & (log.t <= t0 + window_s) & steady
    if not np.any(mask):
        return float("nan")
    t = log.t[mask]
    xt = np.abs(log.e_xt[mask])
    out = np.where(xt > band_m)[0]
    if len(out) == 0:
        return 0.0
    last_out = out[-1]
    if last_out >= len(t) - 1:
        return float("nan")  # still out of band at window end -> did not settle
    return float(t[last_out + 1] - t0)


# --- Acceptance criteria ------------------------------------------------------

@dataclass
class Criterion:
    name: str
    metric: str
    bound: float
    op: str            # "<=", ">=", "==False", "==True"
    unit: str
    required: bool = True


DEFAULT_CRITERIA: List[Criterion] = [
    Criterion("Cross-track RMS", "cross_track_rms", 20.0, "<=", "m"),
    Criterion("Cross-track max", "cross_track_max", 60.0, "<=", "m"),
    Criterion("Altitude-hold RMS", "alt_hold_rms", 5.0, "<=", "m"),
    Criterion("Airspeed-hold RMS", "airspeed_hold_rms", 3.0, "<=", "m/s"),
    Criterion("Throttle saturation", "throttle_sat_pct", 15.0, "<=", "%"),
    Criterion("Bank saturation", "bank_sat_pct", 20.0, "<=", "%"),
    Criterion("Nav position RMSE", "est_pos_rmse", 8.0, "<=", "m"),
    Criterion("Geofence containment", "geofence_breach", 0.0, "==False", "bool"),
    Criterion("Mission complete", "mission_complete", 1.0, "==True", "bool"),
    Criterion("Settling time", "settling_time_s", 30.0, "<=", "s", required=False),
]


@dataclass
class CardResult:
    name: str
    metric: str
    value: float
    bound: float
    unit: str
    passed: bool
    required: bool


@dataclass
class TestCardReport:
    scenario: str
    label: str
    version: str
    passed: bool
    results: List[CardResult]
    metrics: FlightMetrics

    def summary_row(self) -> dict:
        return {"scenario": self.scenario, "label": self.label,
                "passed": self.passed, **self.metrics.as_dict()}


def _evaluate(value, crit: Criterion) -> bool:
    if crit.op == "<=":
        if isinstance(value, float) and np.isnan(value):
            return not crit.required  # unmeasurable -> only fails if required
        return value <= crit.bound
    if crit.op == ">=":
        return value >= crit.bound
    if crit.op == "==False":
        return value is False or value == 0
    if crit.op == "==True":
        return value is True or value == 1
    raise ValueError(f"unknown op {crit.op}")


def grade(metrics: FlightMetrics, criteria: List[Criterion] | None = None) -> TestCardReport:
    criteria = criteria or DEFAULT_CRITERIA
    results: List[CardResult] = []
    all_pass = True
    for c in criteria:
        val = getattr(metrics, c.metric)
        ok = _evaluate(val, c)
        if c.required and not ok:
            all_pass = False
        results.append(CardResult(
            name=c.name, metric=c.metric,
            value=float(val) if not isinstance(val, bool) else float(val),
            bound=c.bound, unit=c.unit, passed=ok, required=c.required,
        ))
    return TestCardReport(
        scenario=metrics.scenario, label=metrics.label, version=CARD_VERSION,
        passed=all_pass, results=results, metrics=metrics,
    )
