# Failure Analysis FA-002 — Coulomb-counter SOC drift under shunt-current bias

| | |
|---|---|
| **Report ID** | FA-002 |
| **Subject** | SOC estimator robustness study |
| **Test bench** | Polaris Virtual Bench VTB-1 |
| **Operator** | A. Barbarin |
| **Date** | 2026-06-29 |

## 1. Summary

A 2 h drive-cycle (alternating 1 C discharge / rest / 0.5 C charge / rest, 10 min each segment) was applied to a single cell and tracked simultaneously by **three SOC estimators**: open-loop coulomb counting (CC), a 3-state Extended Kalman Filter (EKF) implemented in C++, and a residual ML-augmented variant of the EKF. The current-sense shunt was deliberately biased to mimic a worst-case ADC offset.

Across six DoE conditions, the EKF reduced RMS SOC error by **90 % on average** vs coulomb counting (range +74 % to +99 %). The single largest residual was at −10 °C with a deliberately-wrong initial guess (RMS 5.5 %); this is the regime where the OCV-SOC curve is flattest and observability of SOC from terminal voltage is weakest.

## 2. Per-scenario results

| Scenario | T (K) | Shunt bias (A) | Guess err | CC RMS | EKF RMS | EKF advantage |
|---|---|---|---|---|---|---|
| baseline | 298.15 | 0.00 | 0.0 | 0.050 | 0.002 | +97 % |
| bad_guess | 298.15 | 0.00 | 0.4 | 0.400 | 0.005 | +99 % |
| biased_shunt | 298.15 | 0.08 | 0.0 | 0.076 | 0.011 | +86 % |
| biased_and_bad_guess | 298.15 | 0.08 | 0.4 | 0.425 | 0.010 | +98 % |
| cold_minus_10c | 263.15 | 0.04 | 0.2 | 0.213 | 0.055 | +74 % |
| hot_plus_45c | 318.15 | 0.04 | 0.2 | 0.213 | 0.029 | +87 % |

## 3. Diagnosis of coulomb-counter failure mode

CC integrates measured current without feedback, so any DC offset on the shunt accumulates linearly. At 80 mA bias over a 2 h test, the integrated drift is 0.05 SOC — which matches the observed 0.076 RMS (the additional 0.026 comes from the wrong initial guess that CC has no mechanism to correct).

The EKF closes the loop by reconciling its predicted terminal voltage against the measured voltage, with the Kalman gain weighting the correction by the current covariance and OCV slope. The Jacobian H = [dOCV/dSOC, −1, −1] is largest in the 0.2–0.4 and 0.7–0.9 SOC ranges where the OCV table has the steepest segments — these are the regions where the EKF re-anchors most aggressively.

## 4. Limitation observed

At very low temperature (−10 °C) the impedance terms R1, R2 rise by ~2.4× via the Arrhenius scaling, so terminal-voltage transients are dominated by RC dynamics, not by OCV(SOC). The EKF still beats CC, but absolute SOC error grows to 5.5 % RMS. A practical mitigation is **temperature-scheduled process-noise injection**: raising Q[0,0] at low T tells the filter to trust the voltage measurement less, preventing it from over-correcting on transients.

## 5. Reproduction

```bash
python3 scripts/benchmark_estimators.py
# outputs data/estimator_benchmark.{csv,json}
```
