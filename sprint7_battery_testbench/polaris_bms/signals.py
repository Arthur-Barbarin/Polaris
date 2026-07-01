"""Sensor signal models - additive noise, bias drift, quantisation.

Used to make the synthetic test data look like real DAQ output so the
EKF and ML estimators are exercised under realistic conditions.
"""
from __future__ import annotations

import numpy as np


def inject_voltage_noise(
    v: float,
    rng: np.random.Generator,
    std_v: float = 0.002,
    bias_v: float = 0.0,
    lsb: float = 0.0,
) -> float:
    """Add Gaussian noise + bias + optional ADC quantisation."""
    out = v + bias_v + rng.normal(0.0, std_v)
    if lsb > 0:
        out = round(out / lsb) * lsb
    return float(out)


def inject_current_noise(
    i: float,
    rng: np.random.Generator,
    std_a: float = 0.01,
    bias_a: float = 0.0,
) -> float:
    """Shunt-style current measurement noise."""
    return float(i + bias_a + rng.normal(0.0, std_a))
