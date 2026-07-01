"""Pure-Python reference SOC estimators benchmarked against the C++ EKF.

These exist so the benchmark suite can compare three algorithms side-by-side:
  1. CoulombCounter - integrator with no voltage feedback (drifts with ADC bias).
  2. EKF (in polaris_bms.native) - linearised state-space + Kalman update.
  3. MlAugmentedSoc - residual model: EKF mean + a regression correction
     trained on EKF errors from a held-out simulated drive cycle. Currently
     uses a small Random-Forest fit on (V, I, T, base_soc) -> residual.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import numpy as np
from sklearn.ensemble import RandomForestRegressor

from .native import Cell, Ekf
from .signals import inject_current_noise, inject_voltage_noise


@dataclass
class CoulombCounter:
    """Naïve integrator: SOC_{k+1} = SOC_k - I*dt / (Q*3600)."""

    capacity_ah: float = 3.20
    eta_charge: float = 0.995
    soc: float = 1.0

    def reset(self, soc: float) -> None:
        self.soc = float(soc)

    def step(self, current_a: float, dt_s: float, **_: float) -> float:
        eta = self.eta_charge if current_a < 0 else 1.0
        self.soc -= eta * current_a * dt_s / (self.capacity_ah * 3600.0)
        self.soc = float(np.clip(self.soc, 0.0, 1.0))
        return self.soc


def _drive_cycle(n_samples: int, dt_s: float = 1.0) -> np.ndarray:
    """Synthetic charge/discharge profile used for training and validation."""
    t = np.arange(n_samples) * dt_s
    seg = (t // 600) % 4
    out = np.zeros(n_samples)
    out[seg == 0] = 3.2
    out[seg == 1] = 0.0
    out[seg == 2] = -1.6
    out[seg == 3] = 0.0
    return out


class MlAugmentedSoc:
    """EKF + a Random-Forest residual corrector trained on simulated errors.

    Training: run a fresh simulation with known true SOC, feed the EKF
    biased measurements, collect (features, residual=true-ekf) pairs, fit
    a small forest. Inference: at each step, get the EKF SOC then add the
    forest's residual prediction.

    Features kept simple so a real Apple test rig could reproduce them:
      [V_term, I, T_k, EKF_soc].
    """

    def __init__(self, ekf: Ekf):
        self.ekf = ekf
        self.model: Optional[RandomForestRegressor] = None
        self.last_features = np.zeros(4)

    @classmethod
    def trained_on_simulation(
        cls,
        bias_a: float = 0.05,
        dur_s: float = 3600,
        dt_s: float = 1.0,
        n_estimators: int = 60,
        max_depth: int = 6,
        seed: int = 31,
    ) -> "MlAugmentedSoc":
        rng = np.random.default_rng(seed)
        cell = Cell(soc0=1.0, temperature_k=298.15)
        ekf_train = Ekf(soc_guess=0.7, covariance_soc=0.2)
        profile = _drive_cycle(int(dur_s / dt_s), dt_s)
        X, y = [], []
        for i_true in profile:
            v_true = cell.step(float(i_true), dt_s)
            v_meas = inject_voltage_noise(v_true, rng, std_v=0.002)
            i_meas = inject_current_noise(float(i_true), rng, std_a=0.01, bias_a=bias_a)
            ekf_train.step(i_meas, v_meas, 298.15, dt_s)
            X.append([v_meas, i_meas, 298.15, ekf_train.soc])
            y.append(cell.snapshot().soc - ekf_train.soc)
        # Drop warm-up
        X, y = np.array(X[60:]), np.array(y[60:])
        model = RandomForestRegressor(
            n_estimators=n_estimators, max_depth=max_depth,
            random_state=seed, n_jobs=1,
        ).fit(X, y)
        # Fresh EKF for inference
        inference = cls(Ekf(soc_guess=0.5, covariance_soc=0.2))
        inference.model = model
        return inference

    def step(self, current_a: float, v_measured: float, T_k: float, dt_s: float) -> float:
        base = self.ekf.step(current_a, v_measured, T_k, dt_s)
        feats = np.array([v_measured, current_a, T_k, base])
        self.last_features = feats
        if self.model is None:
            return base
        delta = float(self.model.predict(feats.reshape(1, -1))[0])
        return float(np.clip(base + delta, 0.0, 1.0))

    @property
    def soc(self) -> float:
        # Just expose the base EKF SOC + last correction; benchmark uses .step()'s return.
        if self.model is None:
            return self.ekf.soc
        return float(np.clip(self.ekf.soc + self.model.predict(self.last_features.reshape(1, -1))[0], 0.0, 1.0))
