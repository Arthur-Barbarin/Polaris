# Polaris Sprint 9 — Precision-Landing Validation Studio

A closed-loop, vision-guided precision-landing harness: a multirotor flies an
autonomous descent onto a fiducial pad using a downward camera, fusing coarse
GPS with precise-but-intermittent vision (the **GPS→vision handover**), closing
a gated descent-guidance loop with decision-height **go-around** logic. Every
approach is scored against **landing test cards**, and campaigns are
characterised by **Monte-Carlo touchdown dispersion (CEP)** and **PCA+GMM
anomaly triage** over the approaches.

Optimised for the **Flight Test** angle: approach telemetry, quantitative
landing acceptance, dispersion statistics, safe-abort validation, and anomaly
detection over many logged approaches.

> **Honesty note.** The camera model produces **synthetic measurements** —
> pinhole projection of a fiducial's geometry with pixel noise, FOV gating and
> missed detections — **not real image pixels**; no images are rendered or
> processed. The multirotor is a reduced-order, acceleration-limited
> translational model, not a full 6-DOF quadrotor. Nothing here implies real
> flight hardware.

## Architecture

```
   ┌──────────────── scenario (wind / pad offset / GPS bias / occlusion) ─────┐
   ▼                                                                          │
 truth state ─► Camera (pinhole + FOV + noise + dropout) ─► vision (rel-to-pad)
     │          Sensors (GPS coarse, rangefinder, IMU)   ─► GPS / range / accel
     │                                    │
     │                                    ▼
     │                         LandingKF  (predict on IMU;
     │                         update on GPS + range + vision)
     │                                    │  estimate (rel-to-pad pos/vel)
     ▼                                    ▼
  Multirotor RK4 ◄──────────────  LandingGuidance (gated descent state machine:
  (accel-limited)                 ACQUIRE→DESCEND→FLARE, or GO_AROUND)
     │
     ▼
  ApproachLog ─► landing test cards (PASS/FAIL/REJECT) ─► CEP dispersion + PCA/GMM triage
```

## Layout

```
sprint9_precision_landing/
├── polaris_pl/
│   ├── vehicle.py     accel-limited multirotor translational dynamics + RK4
│   ├── pad.py         landing-pad pose (actual vs surveyed)
│   ├── camera.py      pinhole fiducial camera: FOV gate, pixel noise, misses
│   ├── signals.py     coarse GPS (pad-referenced, biasable) + rangefinder + IMU
│   ├── estimator.py   LandingKF: IMU predict; GPS/range/vision updates
│   ├── guidance.py    gated descent state machine + decision-height go-around
│   ├── faults.py      10 scenarios: nominal + 9 fault families
│   ├── simulator.py   closed-loop approach runner -> ApproachLog
│   ├── testcards.py   landing acceptance cards (PASS / FAIL / REJECT)
│   └── dispersion.py  CEP + covariance ellipse; PCA+GMM approach triage
├── tests/test_landing.py     pytest gate (dynamics, camera, handover, guidance, triage)
├── scripts/
│   ├── run_campaign.py  outcomes + CEP + triage -> data/*.json
│   └── verify.py        reproduces every headline number with expected ranges
├── dashboard/app.py    Streamlit: Approach / Test Cards / Dispersion / Triage / Campaign
└── data/               generated campaign.json + triage.json
```

## Quickstart

```bash
pip install -r requirements.txt

python scripts/verify.py                    # sanity-check the physics + metrics
python -m pytest -q                         # 19-test gate
python scripts/run_campaign.py --seeds 20   # campaign -> data/
streamlit run dashboard/app.py              # interactive dashboard
```

## How the GPS→vision handover works

GPS is referenced to the *surveyed* pad location and is noisy (~1.2 m). The
camera measures the vehicle relative to the *actual* pad, and its noise
**shrinks with altitude** — `sigma = hypot(z·pixel_noise/f, floor)` — because a
closer marker is bigger and sharper. So on short final vision is ~15–25× more
precise than GPS and dominates the filter, pulling the touchdown onto the true
pad even when GPS is wrong.

This is exactly why two fault families that would *ruin* a GPS-only landing are
absorbed here:

* **`offset_pad`** — the pad sits 1.8 m E, 1.3 m N from the survey. GPS would
  land you 2.2 m off; with vision the touchdown error is **≈ 0.03 m**.
* **`gps_bias`** — a 2.5 m / 2.0 m GPS bias; touchdown error is still **≈ 0.03 m**.

The **GPS-vision disagreement** — how far apart the two sensors place the
vehicle — is logged as a feature: it is ~1.5 m for nominal (just GPS noise),
~2.8 m for `offset_pad`, ~3.7 m for `gps_bias`. That signal reveals a hidden
pad-survey error *even though the landing succeeded*, and it is what lets the
triage separate the compensated faults.

## Landing test cards (v1.0.0) — three-way outcome

A landing point is scored **PASS** / **FAIL** / **REJECT**, the way flight test
scores a landing:

* **PASS** — landed within every tolerance.
* **FAIL** — landed, but a required card was violated (a landing that should not
  have happened that way).
* **REJECT** — a **go-around**: the guidance correctly refused to land (vision
  lost or not aligned below the decision height). A safe abort, validated
  separately (must climb clear), not a card failure.

| Criterion | Bound |
|---|---|
| Touchdown lateral error | ≤ pad acceptance radius (default 0.5 m) |
| Touchdown sink rate | ≤ 1.0 m/s |
| Max lateral on final | ≤ 2.0 m |
| Vision availability on final | ≥ 70 % |
| Nav error on final | ≤ 0.3 m |

The touchdown card reads the pad's own `touchdown_radius_m`, so a bigger or
smaller pad changes what counts as a good landing.

## Representative campaign (12 seeds/scenario, dt = 0.02 s)

CEP is reported two ways: **precision** (about the sample mean) and **accuracy**
(about the pad), so a steady-wind touchdown **bias** is not hidden.

| Scenario | PASS | FAIL | REJECT | CEP50 prec. [m] | bias [m] | CEP50 accur. [m] |
|---|---|---|---|---|---|---|
| nominal | 12 | | | 0.023 | 0.005 | 0.024 |
| crosswind (steady) | 12 | | | 0.018 | **0.037** | **0.041** |
| offset_pad (pad moved 2.2 m) | 12 | | | 0.021 | 0.005 | 0.022 |
| gps_bias (3.2 m bias) | 12 | | | 0.023 | 0.006 | 0.024 |
| degraded_vehicle (tilt/lag limited) | 12 | | | 0.017 | 0.012 | 0.022 |
| narrow_fov (pad leaves frame on entry) | 12 | | | 0.020 | 0.005 | 0.021 |
| late_acquire (pad seen < 8 m) | 11 | 1 | | 0.024 | 0.008 | 0.021 |
| low_light (35 % detection) | | 12 | | 0.044 | 0.028 | 0.063 |
| gust (late lateral gust) | | | 12 | — | — | — |
| vision_dropout (occluded on final) | | | 12 | | | — |

The studio lands the clean / compensated-fault cases to a **~2 cm precision
CEP**, degrades `low_light` into a card **FAIL** (vision availability 35 % <
70 %), and correctly **rejects** the two unsafe finals via go-around. Note the
`crosswind` row: its precision CEP is 1.8 cm but its **accuracy** CEP is 4.1 cm —
the 3.7 cm steady-wind bias that CEP-about-the-mean would have hidden.

**Triage:** StandardScaler → PCA(6) → GMM buckets each approach into one of ten
modes at **90 % in-sample accuracy** — and **all nine fault families are
identified at 12/12**. The entire 10 % error is `nominal` approaches being
absorbed into the benign clean-landing clusters: `nominal` is defined by the
*absence* of any anomaly signature, so unsupervised clustering has nothing
positive to grab onto — the expected hard case for unsupervised triage, and a
more honest result than a tuned number. (`offset_pad` and `gps_bias` are still
told apart from each other and from the benign cases by the GPS-vision-
disagreement feature.)

`scripts/verify.py` reproduces every headline number above with its expected
physical range; the pytest suite gates the same behaviour on each change.

## Model validation

The model was stress-tested for physical plausibility (the same discipline
applied to Sprint 8), and the fixes are locked in by `verify.py` + pytest:

* **Vision precision improves with altitude, bounded by a floor** — so
  touchdown CEP is realistic (~2 cm), not the unphysical sub-millimetre a
  noise-goes-to-zero model would produce.
* **Steady wind is rejected, not tolerated as droop** — the horizontal loop has
  integral action, so a constant crosswind lands centred (early proportional-
  only versions stalled the descent in a hover trap; caught and fixed).
* **Go-arounds actually abort and climb clear** — decision-height logic converts
  unsafe finals into REJECT outcomes rather than bad landings.

A second **expert audit pass** (hunting for dead inputs, inert couplings and
metric blind spots) drove four more fixes, each locked by a regression guard:

* **CEP now reports accuracy, not just precision** — about the pad as well as
  the sample mean, so the ~3.7 cm steady-wind touchdown *bias* is surfaced
  instead of hidden inside a displaced mean.
* **The pad's `touchdown_radius_m` is load-bearing** — the touchdown card reads
  it instead of a hardcoded 0.5 m (it was a dead config knob).
* **The airframe is injectable through `simulate()`** — the `Multirotor`
  envelope was hardcoded and unexercised; a `degraded_vehicle` scenario now
  drives it (tilt/lag-limited → visibly worse tracking).
* **The camera FOV limit and one dead triage feature were addressed** — a
  `narrow_fov` scenario exercises the field-of-view gate (previously inert for
  the approach envelope), and the schedule-limited `max_sink` feature (std 0.01)
  was dropped from the triage set.

## Why this sprint (Flight Test)

Deepens the autonomy / closed-loop story from Sprint 8 into **perception in the
loop**, and targets the Zipline **Flight Test** JD directly: approach telemetry
and flight-log-style analysis, quantitative landing acceptance (touchdown CEP,
sink rate, glideslope), **safe-abort / go-around validation**, and anomaly
detection over a campaign of logged approaches. Reuses the Polaris closed-loop
simulator, Kalman-filter and PCA+GMM triage idioms (Sprints 3/7/8) applied to a
vision-guided landing device-under-test.

## CV bullets

- Built a **closed-loop vision-guided precision-landing studio** in Python: an
  accel-limited multirotor flying an autonomous descent onto a fiducial pad,
  with a **pinhole camera perception model** (FOV gating, altitude-scaled pixel
  noise, missed detections, occlusion) feeding a **Kalman filter that fuses
  coarse GPS with precise intermittent vision** — the GPS→vision handover that
  drives touchdown to a **~2 cm CEP**.
- Demonstrated **fault absorption via sensor handover**: a 2.2 m pad-survey
  error and a 3.2 m GPS bias that would each wreck a GPS-only landing are
  corrected to ~3 cm touchdown error by vision; logged the **GPS-vision
  disagreement** as the feature that still flags the hidden fault post-landing.
- Wrote a **gated descent-guidance state machine** (acquire → descend → flare)
  with a **decision-height go-around**, and a three-way **PASS / FAIL / REJECT**
  landing-test-card engine scoring touchdown CEP, sink rate, lateral corridor,
  nav accuracy and vision availability; a **Monte-Carlo dispersion campaign**
  reports CEP50/CEP95 and a covariance ellipse per condition.
- Added **PCA + Gaussian-Mixture anomaly triage** over approaches (**all nine
  fault families 100 %**, 90 % overall — nominal being the hard baseline case),
  a **`verify` script** that reproduces every headline number against its
  expected physical range, and a **19-test pytest gate** (including a "never
  lands blind" safety guard) — after **two physical-plausibility audits** that
  caught and fixed an unphysical sub-millimetre CEP, a wind-induced hover trap,
  a precision-vs-accuracy CEP blind spot, and several dead / inert config knobs.

## JD keyword coverage

precision landing, autonomous landing, vision-guided, perception, fiducial /
marker detection, pinhole camera model, sensor fusion, GPS/vision handover,
Kalman filter, state estimation, guidance state machine, go-around / rejected
landing, decision height, touchdown dispersion, CEP, Monte-Carlo, flight-log /
telemetry analysis, anomaly detection, PCA, GMM, verification & validation,
Python, pytest.

---

Sprint 9 of the [Polaris Decision Modeling Studio](../README.md).
*Engineering clarity for complex futures.*
