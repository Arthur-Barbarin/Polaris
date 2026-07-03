# Polaris Sprint 8 — Autonomous UAV Flight-Test Validation Harness

A closed-loop fixed-wing flight-test harness: a **reduced-order fixed-wing UAV**
flown by a **cascaded autopilot** that closes its loops on a **navigation EKF**,
driven through **fault-injection campaigns**, graded by a **versioned
flight-test-card engine**, and triaged by a **PCA + Gaussian-Mixture** anomaly
classifier over the resulting flight logs.

The point of the sprint: demonstrate the validation toolchain a flight-test /
autonomy engineer builds around a vehicle that behaves autonomously — a control
loop that actually closes on estimated state, flight-log-style telemetry, and
automated pass/fail acceptance — rather than open-loop sensor logging or pure
simulation output.

> **Honesty note.** Every measurement here is **synthetic simulator output**,
> not captured from real flight hardware. The vehicle is a *guidance-level*
> reduced-order model (Beard & McLain style), not full 6-DOF aerodynamics.
> Nothing in this repo implies a physical aircraft was flown.

## Architecture

```
        ┌────────────────────────────────────────────────────────┐
        │  Fault-injection scenario (wind / sensor / actuator)    │
        └───────────────┬────────────────────────────────────────┘
                        ▼
   truth ground velocity ─► SensorSuite ─► noisy GPS / baro / pitot / heading
                        │                        │
                        │                        ▼
                        │                   NavEKF  (predict + update)
                        │              [pn pe vn ve h], GPS-dropout coasting
                        │                        │  estimate (pos, alt, course)
                        ▼                        ▼
        Airframe RK4 dynamics ◄────────── Autopilot (cascaded PID)
        coordinated-turn kinematics       lateral path-follow · alt hold · airspeed
                        │
                        ▼
                  FlightLog (synthetic telemetry)
                        │
          ┌─────────────┴──────────────┐
          ▼                            ▼
   Test-card engine            PCA → GMM anomaly triage
   (versioned pass/fail)       (bucketize runs into fault modes)
```

## Layout

```
sprint8_flight_test_harness/
├── cpp/                 C++ inner loop (dynamics + autopilot) + flat C ABI
│   ├── flight_core.{hpp,cpp}   RK4 step + cascaded autopilot command law
│   ├── c_api.cpp               extern "C" entry points (ft_step, ft_control)
│   └── Makefile                -> ../build/libpolaris_ft.{so|dylib}
├── polaris_ft/
│   ├── vehicle.py       reduced-order fixed-wing dynamics + RK4 (with wind)
│   ├── mission.py       waypoints, legs, geofence, cross-track geometry
│   ├── controller.py    cascaded autopilot (path-follow / alt / airspeed)
│   ├── estimator.py     NavEKF fusing GPS + baro + airspeed/heading
│   ├── signals.py       synthetic sensor noise / bias / GPS-rate model
│   ├── faults.py        7 scenarios: nominal + 6 fault families
│   ├── simulator.py     closed-loop runner -> FlightLog (backend=python|native)
│   ├── native.py        ctypes wrapper around libpolaris_ft
│   ├── testcards.py     metrics + versioned pass/fail acceptance cards
│   └── triage.py        StandardScaler -> PCA -> GMM anomaly triage
├── tests/
│   ├── test_harness.py         pytest gate (dynamics, guidance, EKF, cards, triage)
│   └── test_native_parity.py   C++ vs Python parity (auto-skips if unbuilt)
├── scripts/
│   ├── run_campaign.py     full campaign -> data/*.json + summary table
│   ├── verify.py           reproduces every headline number with expected ranges
│   └── benchmark_native.py C++ vs Python inner-loop latency
├── dashboard/app.py     Streamlit: Flight Track / Test Cards / Campaign / Triage
└── data/                generated campaign.json + triage.json
```

## Quickstart

```bash
pip install -r requirements.txt

cd cpp && make && cd ..                         # build the C++ inner loop (optional)
python scripts/verify.py                       # sanity-check the physics + metrics
python -m pytest -q                            # 23-test gate (incl. C++ parity)
python scripts/run_campaign.py --seeds 8       # full fault campaign -> data/
python scripts/benchmark_native.py             # C++ vs Python inner-loop latency
streamlit run dashboard/app.py                 # interactive dashboard
```

The C++ core is **optional** — the whole harness runs in pure Python if
`libpolaris_ft` is not built. Pass `backend="native"` to `simulate()` (or set it
in the dashboard) to run the inner loop in C++.

## What the loop actually closes on

The autopilot never sees truth. Each control tick it consumes the **EKF
estimate** of position, altitude and ground course, plus the raw (biased, if
faulty) airspeed reading. So sensor and estimator faults propagate into
closed-loop behaviour exactly as they would on a real aircraft — a biased pitot
makes the airspeed loop fly the *wrong* true speed; a GPS dropout forces the
EKF to coast on its airspeed/heading pseudo-measurement.

* **Lateral:** straight-line path following (Beard & McLain eq. 10.8),
  `chi_c = chi_path − chi_inf·(2/π)·atan(k·e_xt)`, then course-hold → bank.
* **Longitudinal:** proportional altitude-hold → commanded flight-path angle.
* **Airspeed:** PI throttle controller with anti-windup.
* **Estimator:** EKF on `[pn, pe, vn, ve, h]`; GPS position/velocity + baro are
  linear updates, the airspeed+heading velocity pseudo-measurement is the
  nonlinear (extended) update that keeps the horizontal solution bounded during
  GPS dropout. `psi_dot = g/V·tan(phi)` coordinated-turn kinematics verified
  against the analytic turn radius `V²/(g·tan φ)`.

## C++ inner loop (real-time / embedded core)

The dynamics RK4 step and the cascaded autopilot command law — the part that on
a real airframe runs deterministically every control tick on the flight
controller — are ported to **C++** (`cpp/flight_core.cpp`) behind a flat **C
ABI** (`ft_step`, `ft_control`), called from Python through a `ctypes` wrapper
(`polaris_ft/native.py`). `simulate(..., backend="native")` swaps the Python
inner loop for the C++ one; everything else (sensors, EKF, test cards, triage)
is unchanged.

* **Parity is verified, not assumed.** `test_native_parity.py` checks a single
  RK4 step and a single autopilot command against the Python implementation over
  thousands of random states — both match to **< 1e-9** (machine epsilon).
  Building this test immediately caught a real bug: the first C++ RK4 draft
  chained the stage evaluations (`k3` from the `k2`-state) instead of evaluating
  every stage from the original state; parity failed at ~1e-2 until fixed, then
  dropped to ~1e-13.
* Whole-flight trajectories track to **< 1 m** over a multi-km mission between
  backends (bit-exact divergence isn't expected — numpy and libm differ by ~1
  ULP on transcendentals, which compounds through the feedback loop), and the
  pass/fail verdict is identical across backends for all 7 scenarios.
* **Real-time head-room:** the C++ step runs at ~10 µs/call including Python↔
  ctypes marshalling (~4× the Python path; native-to-native it is sub-µs) — at a
  50 Hz control loop that is **~0.05 % of the 20 ms budget**.

## Test-card acceptance (v1.0.0)

Tracking-error cards are evaluated on **straight legs only** — launch and
turn-transition windows are excluded, standard flight-test practice, since a
fixed-wing physically cannot corner inside its turn radius while following
straight-line legs.

| Criterion | Bound | Required |
|---|---|---|
| Cross-track RMS | ≤ 20 m | yes |
| Cross-track max | ≤ 60 m | yes |
| Altitude-hold RMS | ≤ 10 m | yes |
| Airspeed-hold RMS | ≤ 3 m/s | yes |
| Throttle saturation | ≤ 15 % | yes |
| Bank saturation | ≤ 20 % | yes |
| Nav position RMSE | ≤ 8 m | yes |
| Geofence containment | no breach | yes |
| Mission complete | true | yes |
| Settling time after disturbance | ≤ 30 s | advisory |

## Representative campaign results (5 seeds/scenario, dt = 0.05 s)

| Scenario | Pass | XT RMS [m] | XT max [m] | Alt RMS [m] | Va RMS [m/s] | Nav RMSE [m] |
|---|---|---|---|---|---|---|
| nominal | **5/5** | 1.25 | 15.4 | 2.23 | 0.05 | 1.51 |
| elevator_loss (mild) | **5/5** | 1.25 | 15.4 | 0.73 | 0.05 | 1.50 |
| wind_step (8 m/s crosswind) | 0/5 | 10.6 | 108.8 | 2.34 | 0.05 | 2.84 |
| wind_shear (12 m/s ramp) | 0/5 | 6.7 | 90.3 | 2.16 | 0.05 | 5.84 |
| gps_dropout (30 s) | 0/5 | 16.7 | 111.5 | 2.20 | 0.05 | **18.9** |
| airspeed_bias (−4 m/s pitot) | 0/5 | 2.75 | 41.2 | 2.98 | **4.00** | 2.21 |
| aileron_loss (55 % roll auth.) | 0/5 | **35.1** | 203.9 | 2.21 | 0.05 | 1.51 |

The harness passes the nominal mission and a *mild* elevator degradation (whose
gentle altitude demands stay inside acceptance), and fails the five fault
families that violate a required card — each failing on the metric that
physically corresponds to the injected fault (nav RMSE for GPS dropout,
airspeed error for pitot bias, cross-track for the aileron fault, and so on).

**EKF value:** on the nominal run the fused position RMSE is ≈1.5 m against a
2 m/axis raw-GPS fix; during a 30 s GPS dropout the horizontal error stays
bounded (max ≈110 m, no divergence) because the airspeed/heading pseudo-
measurement constrains velocity while GPS is unavailable — and the mission
still completes.

**Triage:** StandardScaler → PCA(4) → GMM auto-buckets each run into one of the
seven modes at **100 % in-sample accuracy** on this campaign. The fault
families are well separated by construction, so this reflects in-sample
separability of the synthetic scenarios, not a generalization claim on real
flight data.

`scripts/verify.py` reproduces every headline number above with its expected
physical range, and the pytest suite gates the same behaviour on each change.

## Why this sprint

Closes the single gap that recurs across Zipline's **Electrical Engineer**,
**Hardware Test**, and **Flight Test Engineer** intern JDs, and is the weakest
link in the rest of the Polaris portfolio: no prior project tests or validates a
system that behaves **autonomously / closed-loop** using flight-log-style
telemetry — only pure simulation output or open-loop sensor DAQ.

* **Flight Test:** a controller that closes on estimated state, synthetic flight
  logs, automated flight-test cards with pass/fail gating, and anomaly detection
  over a test campaign.
* **Hardware Test:** ownership of a reusable test asset end-to-end (concept →
  build → automated validation → recommendation), with actuator/sensor faults in
  the loop rather than sensor logging alone.
* **Electrical Engineer:** a real-time-style estimation + control loop and
  automated regression-style test coverage.

Reuses the **PCA + GMM** anomaly-triage pattern from Sprint 3 / Sprint 7 and the
sensor-signal modelling approach from Sprint 7, applied to a fixed-wing DUT.

## CV bullets

- Built a **closed-loop fixed-wing flight-test validation harness** in Python: a
  reduced-order UAV flown by a cascaded path-following / altitude / airspeed
  autopilot that closes its loops on a **navigation EKF** (GPS + barometer +
  airspeed/heading fusion), plus a **versioned test-card engine** that grades
  each run pass/fail on cross-track error, altitude/airspeed hold, control
  saturation, nav accuracy, and geofence containment — evaluated on straight
  legs per flight-test practice.
- Ran **fault-injection campaigns** (crosswind step, wind shear, 30 s GPS
  dropout, biased pitot, degraded aileron/elevator authority) across seeded
  runs; the harness passes the nominal mission and correctly fails each fault on
  its physically-corresponding metric. Quantified estimator value: **EKF nav
  RMSE ≈1.5 m vs a 2 m/axis GPS fix**, and **bounded (non-divergent) horizontal
  error through GPS dropout** via an airspeed/heading pseudo-measurement.
- Developed a **PCA + Gaussian-Mixture anomaly-triage pipeline** that
  auto-buckets flight logs into seven nominal/fault modes at 100 % in-sample
  accuracy on the synthetic campaign, reusing the Sprint 3 / Sprint 7 triage
  pattern on a fixed-wing device-under-test.
- Ported the **inner control loop (RK4 dynamics + cascaded autopilot) to C++**
  behind a flat **C ABI** with a Python **ctypes** binding, and verified
  **bit-level parity** with the Python reference (< 1e-9 per step over thousands
  of random states — the parity test caught a real RK4 stage-evaluation bug);
  the C++ step runs in ~10 µs (≈0.05 % of a 50 Hz control budget).
- Backed the whole harness with a **`verify` script** (reproduces every headline
  number against its expected physical range, e.g. coordinated-turn radius
  `V²/(g·tan φ)`) and a **23-test pytest gate** spanning dynamics, guidance,
  estimator, test cards, triage, and C++/Python parity.

## JD keyword coverage

closed-loop control, autonomous vehicle, flight test, test cards, pass/fail
acceptance, guidance, path following, cascaded PID, autopilot, state estimation,
Extended Kalman Filter, sensor fusion, GPS/INS, fault injection, anomaly
detection, PCA, GMM, telemetry / flight-log analysis, geofence, regression
testing, pytest, Python, C, C++, C ABI, ctypes, real-time / embedded control
loop, verification & validation, RK4, coordinated turn.

---

Sprint 8 of the [Polaris Decision Modeling Studio](../README.md).
*Engineering clarity for complex futures.*
