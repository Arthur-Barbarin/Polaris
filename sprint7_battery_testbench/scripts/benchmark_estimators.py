"""Side-by-side SOC estimator benchmark.

Runs a multi-condition campaign (cold/hot, biased/clean sensors, wrong/right
initial guess) and writes a CSV + JSON summary of the error envelopes.

  python3 scripts/benchmark_estimators.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from polaris_bms import Cell, CoulombCounter, Ekf
from polaris_bms.estimators import MlAugmentedSoc
from polaris_bms.signals import inject_current_noise, inject_voltage_noise

OUT_DIR = REPO / "data"
OUT_DIR.mkdir(exist_ok=True)


def seed_guess(true_soc: float, guess_err: float) -> float:
    """Initial SOC handed to every estimator, guarded to the physical range.

    The guard exists only to keep the seed inside [0, 1]. It must never move the
    seed for a scenario that declares a guess error, and must never introduce one
    for a scenario that declares none. A previous version clipped to (0.05, 0.95);
    since every scenario starts the cell at soc0 = 1.0, that upper bound silently
    seeded all three estimators 0.05 low in every run, including the "clean"
    baseline, and inflated the EKF's measured advantage over open-loop coulomb
    counting. See FA-002 rev B and integration_campaign_2026-09 finding F1-5.
    """
    return float(np.clip(true_soc - guess_err, 0.0, 1.0))


@dataclass
class Result:
    scenario: str
    duration_s: float
    temperature_k: float
    current_bias_a: float
    initial_guess_err: float
    cc_rms: float
    cc_max: float
    ekf_rms: float
    ekf_max: float
    ml_rms: float
    ml_max: float
    ekf_advantage_pct: float
    ml_advantage_pct: float


def _run_scenario(
    label: str,
    *,
    temperature_k: float,
    bias_a: float,
    guess_err: float,
    profile_a: np.ndarray,
    ml_estimator: MlAugmentedSoc,
    dt: float = 1.0,
    seed: int = 13,
) -> Result:
    rng = np.random.default_rng(seed)
    cell = Cell(soc0=1.0, temperature_k=temperature_k)
    true_init = cell.snapshot().soc
    init_guess = seed_guess(true_init, guess_err)
    ekf = Ekf(soc_guess=init_guess, covariance_soc=0.2)
    cc = CoulombCounter(capacity_ah=cell.snapshot().q_now_ah, soc=init_guess)
    # Reset the ML estimator's internal EKF for this scenario.
    ml_estimator.ekf = Ekf(soc_guess=init_guess, covariance_soc=0.2)

    n = len(profile_a)
    true = np.empty(n)
    e_ekf = np.empty(n)
    e_cc = np.empty(n)
    e_ml = np.empty(n)

    for k, i_true in enumerate(profile_a):
        v_true = cell.step(float(i_true), dt)
        v_meas = inject_voltage_noise(v_true, rng, std_v=0.002)
        i_meas = inject_current_noise(float(i_true), rng, std_a=0.01, bias_a=bias_a)
        ekf.step(i_meas, v_meas, temperature_k, dt)
        cc.step(i_meas, dt)
        ml = ml_estimator.step(i_meas, v_meas, temperature_k, dt)
        true[k] = cell.snapshot().soc
        e_ekf[k] = ekf.soc
        e_cc[k] = cc.soc
        e_ml[k] = ml

    warm = int(60 / dt)
    err_ekf = true[warm:] - e_ekf[warm:]
    err_cc = true[warm:] - e_cc[warm:]
    err_ml = true[warm:] - e_ml[warm:]
    cc_rms = float(np.sqrt(np.mean(err_cc ** 2)))
    cc_max = float(np.max(np.abs(err_cc)))
    ekf_rms = float(np.sqrt(np.mean(err_ekf ** 2)))
    ekf_max = float(np.max(np.abs(err_ekf)))
    ml_rms = float(np.sqrt(np.mean(err_ml ** 2)))
    ml_max = float(np.max(np.abs(err_ml)))
    adv_ekf = 100.0 * (1.0 - ekf_rms / cc_rms) if cc_rms > 0 else 0.0
    adv_ml = 100.0 * (1.0 - ml_rms / cc_rms) if cc_rms > 0 else 0.0

    return Result(
        scenario=label,
        duration_s=n * dt,
        temperature_k=temperature_k,
        current_bias_a=bias_a,
        initial_guess_err=guess_err,
        cc_rms=cc_rms,
        cc_max=cc_max,
        ekf_rms=ekf_rms,
        ekf_max=ekf_max,
        ml_rms=ml_rms,
        ml_max=ml_max,
        ekf_advantage_pct=adv_ekf,
        ml_advantage_pct=adv_ml,
    )


def _profile_mixed(dur_s: float, dt: float = 1.0) -> np.ndarray:
    """Drive cycle: alternating 1C discharge, rest, 0.5C charge, rest."""
    n = int(dur_s / dt)
    t = np.arange(n) * dt
    seg = (t // 600) % 4   # four 10-min segments
    out = np.zeros(n)
    out[seg == 0] =  3.2   # 1C discharge
    out[seg == 1] =  0.0
    out[seg == 2] = -1.6   # 0.5C charge
    out[seg == 3] =  0.0
    return out


def main() -> None:
    profile = _profile_mixed(3600 * 2)        # 2-hour drive cycle
    print("Training ML residual corrector on a held-out simulated cycle...")
    ml = MlAugmentedSoc.trained_on_simulation(bias_a=0.05, dur_s=3600)
    scenarios = [
        ("baseline_25c",            dict(temperature_k=298.15, bias_a=0.0,  guess_err=0.0)),
        ("bad_guess_25c",           dict(temperature_k=298.15, bias_a=0.0,  guess_err=0.4)),
        ("biased_shunt_25c",        dict(temperature_k=298.15, bias_a=0.08, guess_err=0.0)),
        ("biased_and_bad_guess",    dict(temperature_k=298.15, bias_a=0.08, guess_err=0.4)),
        ("cold_minus_10c",          dict(temperature_k=263.15, bias_a=0.04, guess_err=0.2)),
        ("hot_plus_45c",            dict(temperature_k=318.15, bias_a=0.04, guess_err=0.2)),
    ]
    results: List[Result] = []
    for name, kw in scenarios:
        r = _run_scenario(name, profile_a=profile, ml_estimator=ml, **kw)
        results.append(r)
        print(
            f"  {name:24s}  CC rms={r.cc_rms:.4f}  EKF rms={r.ekf_rms:.4f}  "
            f"ML rms={r.ml_rms:.4f}  EKF adv={r.ekf_advantage_pct:+.1f}%  "
            f"ML adv={r.ml_advantage_pct:+.1f}%"
        )

    # Persist
    json_path = OUT_DIR / "estimator_benchmark.json"
    csv_path = OUT_DIR / "estimator_benchmark.csv"
    with json_path.open("w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        w.writeheader()
        for r in results:
            w.writerow(asdict(r))

    mean_ekf = float(np.mean([r.ekf_advantage_pct for r in results]))
    mean_ml = float(np.mean([r.ml_advantage_pct for r in results]))
    print(f"\nMean EKF advantage vs coulomb counting: {mean_ekf:+.1f}%")
    print(f"Mean ML-augmented advantage vs coulomb counting: {mean_ml:+.1f}%")
    print(f"Wrote {json_path.relative_to(REPO)} and {csv_path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
