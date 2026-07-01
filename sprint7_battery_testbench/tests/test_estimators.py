"""Side-by-side estimator benchmark - EKF should beat coulomb counting
under sensor bias and a wrong initial guess."""
from __future__ import annotations

import numpy as np
import pytest

from polaris_bms import Cell, Ekf, CoulombCounter
from polaris_bms.signals import inject_voltage_noise, inject_current_noise


def _run(true_soc0=1.0, ekf_guess=0.6, bias_a=0.05, dur_s=1800, dt=1.0,
         current_amp=1.6, rng=None):
    rng = rng or np.random.default_rng(7)
    cell = Cell(soc0=true_soc0, temperature_k=298.15)
    ekf = Ekf(soc_guess=ekf_guess, covariance_soc=0.2)
    cc = CoulombCounter(capacity_ah=cell.snapshot().q_now_ah, soc=ekf_guess)
    true, ekf_est, cc_est = [], [], []
    t = 0.0
    while t < dur_s:
        i_true = current_amp + 0.2 * np.sin(t / 60.0)   # mild profile variation
        v_true = cell.step(i_true, dt)
        v_meas = inject_voltage_noise(v_true, rng, std_v=0.002)
        i_meas = inject_current_noise(i_true, rng, std_a=0.01, bias_a=bias_a)
        ekf.step(i_meas, v_meas, 298.15, dt)
        cc.step(i_meas, dt)
        true.append(cell.snapshot().soc)
        ekf_est.append(ekf.soc)
        cc_est.append(cc.soc)
        t += dt
    return np.array(true), np.array(ekf_est), np.array(cc_est)


def test_ekf_converges_under_bad_initial_guess():
    true, ekf_est, _ = _run(true_soc0=1.0, ekf_guess=0.5)
    # After half the run the EKF must have closed most of the 0.5 SOC gap.
    half = len(true) // 2
    err = np.mean(np.abs(true[half:] - ekf_est[half:]))
    assert err < 0.05, f"EKF residual {err:.3f} too large"


def test_ekf_beats_coulomb_counting_with_current_bias():
    true, ekf_est, cc_est = _run(bias_a=0.08)
    ekf_err = float(np.mean(np.abs(true - ekf_est)))
    cc_err = float(np.mean(np.abs(true - cc_est)))
    # EKF should be at least 25% better than CC under bias.
    assert ekf_err < 0.75 * cc_err, f"EKF {ekf_err:.3f} vs CC {cc_err:.3f}"
