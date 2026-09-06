# Failure Analysis FA-002 — Coulomb-counter SOC drift under shunt-current bias

| | |
|---|---|
| **Report ID** | FA-002 |
| **Subject** | SOC estimator robustness study |
| **Test bench** | Polaris Virtual Bench VTB-1 |
| **Operator** | A. Barbarin |
| **Date** | 2026-06-29 (rev B, 2026-09-06) |
| **Revision** | B — headline result withdrawn and replaced, see §0 |

## 0. Revision notice (rev B, 2026-09-06)

Rev A of this report claimed the EKF reduced RMS SOC error by **90 % on average**
versus coulomb counting. **That figure was an artefact of a seeding defect in the
benchmark, and is withdrawn.**

`scripts/benchmark_estimators.py:62` read

```python
init_guess = float(np.clip(true_init - guess_err, 0.05, 0.95))
```

Every scenario starts the cell at `soc0 = 1.0`, so whenever `guess_err` was small
the **upper** bound of that clip silently handed all three estimators a seed of
0.95 against a true SOC of 1.00 — an unrequested 0.05 initialisation error, in
every scenario, including the `baseline_25c` case whose own table row declares a
guess error of 0.0. Open-loop coulomb counting has no mechanism to recover from a
seed error, so it carried that 0.05 for the whole run. The EKF re-anchors on
voltage within seconds and did not. The gap between them was therefore not a
measurement of filter quality; it was the size of the injected handicap.

Measured, with everything else unchanged (`integration_campaign_2026-09`,
finding F1-5):

| condition | CC RMS with the clip | CC RMS without it |
|---|---|---|
| baseline, **zero** shunt bias | 0.0496 | 0.0005 |
| biased shunt, 0.08 A | 0.0761 | 0.0285 |

The bound was corrected to the physical SOC range `(0.0, 1.0)` and the campaign
re-run. §2 onward are the corrected results. The corrected picture is narrower
and, in two scenarios, unfavourable to the EKF. It is also the true one.

Rev A's §3 diagnosis — "the integrated drift is 0.05 SOC ... the additional 0.026
comes from the wrong initial guess" — had the two terms the right size but the
wrong way round, and attributed the seed error to a scenario its own table says
had none.

## 1. Summary

A 2 h drive-cycle (alternating 1 C discharge / rest / 0.5 C charge / rest, 10 min
each segment) was applied to a single cell and tracked simultaneously by **three
SOC estimators**: open-loop coulomb counting (CC), a 3-state Extended Kalman
Filter (EKF) implemented in C++, and a residual ML-augmented variant of the EKF.
Six DoE conditions vary temperature, shunt-current bias, and initial-guess error.

The corrected result is that the EKF's advantage is **conditional, not general**:

- Where the seed is wrong, it is decisive: **+98.7 %** and **+97.7 %** RMS
  reduction in the two `guess_err = 0.4` scenarios.
- At temperature extremes it holds: **+74.3 %** at −10 °C, **+86.6 %** at +45 °C.
- On a clean run it does **not** help: CC 0.0002 vs EKF 0.0003. Both are
  negligible and the ratio between two near-zero numbers is not meaningful.
- Under a **pure shunt bias with a correct seed it is twice as bad as open-loop
  counting**: CC 0.0287 vs EKF 0.0575. See §4.

No single average is quoted, because averaging percentage advantages across
scenarios whose baseline error spans 0.0002 to 0.4252 is dominated by the cases
where the denominator is near zero.

## 2. Per-scenario results

Regenerated 2026-09-06 with the corrected seeding, `data/estimator_benchmark.json`.

| Scenario | T (K) | Shunt bias (A) | Guess err | CC RMS | EKF RMS | ML RMS | EKF vs CC |
|---|---|---|---|---|---|---|---|
| baseline_25c | 298.15 | 0.00 | 0.0 | 0.0002 | 0.0003 | 0.0037 | −9.7 % |
| bad_guess_25c | 298.15 | 0.00 | 0.4 | 0.3998 | 0.0053 | 0.0030 | **+98.7 %** |
| biased_shunt_25c | 298.15 | 0.08 | 0.0 | 0.0287 | 0.0575 | 0.0525 | **−100.0 %** |
| biased_and_bad_guess | 298.15 | 0.08 | 0.4 | 0.4252 | 0.0100 | 0.0086 | **+97.7 %** |
| cold_minus_10c | 263.15 | 0.04 | 0.2 | 0.2125 | 0.0546 | 0.0549 | +74.3 % |
| hot_plus_45c | 318.15 | 0.04 | 0.2 | 0.2125 | 0.0286 | 0.0249 | +86.6 % |

For reference, the same table under rev A's defective seeding read CC 0.0498 /
0.3998 / 0.0763 / 0.4252 / 0.2125 / 0.2125 and EKF advantages of +96.9 / +98.7 /
+86.3 / +97.7 / +74.3 / +86.6 %. The three scenarios with a large declared guess
error are unaffected, because there the injected 0.05 was swamped by the declared
0.4 or 0.2. Only the two scenarios that were supposed to be clean moved — which
is exactly the signature of a seeding defect.

## 3. What the coulomb counter actually does

CC integrates measured current without feedback, so any DC offset on the shunt
accumulates linearly and monotonically. At 80 mA over a 2 h test the integrated
drift reaches ≈0.053 SOC by the end of the run; taken as an RMS over the trace
after the 60 s warm-up window, that is the measured **0.0287**. With no bias and
a correct seed, CC is limited only by the zero-mean current noise it averages
out, and lands at **0.0002**.

This is worth stating plainly because it is the opposite of the folklore: on a
short, well-instrumented, correctly-initialised run, open-loop coulomb counting
is an excellent SOC estimator. It fails on **seed error** (which it can never
correct) and on **sensor bias** (which it integrates). Those are the two
conditions a closed-loop estimator exists to handle.

## 4. Where the EKF fails, and why

The EKF handles seed error exactly as designed: it reconciles predicted terminal
voltage against measured voltage, and the Kalman gain re-anchors SOC through the
Jacobian `H = [dOCV/dSOC, −1, −1]`, which is largest in the 0.2–0.4 and 0.7–0.9
SOC ranges where the OCV table is steepest.

It does **not** handle shunt bias. Its state vector is
`x = [SOC, v_rc1, v_rc2]` — **there is no current-bias state**, so a DC offset on
the current measurement is not observable to the filter. It enters the prediction
step every sample and the filter has no term with which to attribute the
resulting voltage residual to the sensor rather than to the cell. Measured, the
EKF ends at 0.0575 RMS against CC's 0.0287 on that scenario, i.e. it converts a
bias the counter merely integrates into a larger steady-state error.

**Why it is worse rather than merely equal is not established by this campaign**
and is recorded as an open question. The obvious candidate is the process-noise /
measurement-noise balance (`covariance_soc = 0.2` at seed) causing the filter to
over-trust a voltage signal whose residual is being driven by an unmodelled input,
but that has not been tested. The standard remedy — augmenting the state with a
current-bias term, giving a 4-state filter — is a design change, not a defect fix,
and was deliberately not made here.

At −10 °C the impedance terms R1, R2 rise by ≈2.4× via the Arrhenius scaling, so
terminal-voltage transients are dominated by RC dynamics rather than by OCV(SOC).
The EKF still beats CC there because the scenario carries a 0.2 seed error, but
its absolute error grows to 5.5 % RMS. A practical mitigation is
temperature-scheduled process-noise injection: raising Q[0,0] at low T tells the
filter to trust the voltage measurement less.

## 5. Reproduction

```bash
python3 scripts/benchmark_estimators.py
# outputs data/estimator_benchmark.{csv,json}
```

To see the rev A defect rather than take it on trust:

```bash
python3 integration_campaign_2026-09/tools/p1_fa002_clip.py
```

which re-runs two scenarios with the clip as rev A had it and with the corrected
bound, changing nothing else.

## 6. Limitations

- Single cell, deterministic simulation, synthetic sensor noise. No cell-to-cell
  variability and no real ADC behaviour.
- `baseline_25c` now seeds the estimators with the *exact* true SOC, which is
  what a declared guess error of 0.0 means but is not physically realistic. A
  better experiment would start the cell at `soc0 = 0.9` so that a modest,
  *declared* seed error can be applied without the guard ever binding. That is a
  design change and is left open.
- The ML-augmented variant is not analysed here. Its advantage column is
  unstable for the same denominator reason as the EKF's, and on `biased_shunt_25c`
  it inherits the EKF's failure.
- No test in this sprint locks any of these numbers. Until one does, the same
  class of silent drift that produced rev A can recur.
