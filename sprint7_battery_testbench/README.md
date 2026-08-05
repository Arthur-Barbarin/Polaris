# Polaris Sprint 7 — Battery Cell Characterization & SOC/SOH Estimation Testbench

A full-stack battery validation testbench: **C++ Thévenin equivalent-circuit cell model**, **virtual SCPI instrument server**, **pytest-driven characterization suite** (HPPC, OCV-SOC, CC-CV cycling), **Extended Kalman Filter SOC estimator in C++**, and a **PCA + Gaussian Mixture failure triage** pipeline that auto-bucketizes cycling anomalies into named degradation modes.

Designed to demonstrate the validation toolchain an Apple Battery Quality / Hardware System Validation engineer would build: physics-based device-under-test simulation, hardware-style instrument abstraction, automated characterization with DoE sweeps, and AI/ML-augmented anomaly triage on the resulting test data.

## Architecture

```
                  ┌─────────────────────────────────────────┐
                  │            pytest test suites           │
                  │  test_cell_model · test_hppc            │
                  │  test_scpi_interface · test_estimators  │
                  └────────────┬────────────────────────────┘
                               │ ScpiClient (TCP)
                               ▼
                  ┌─────────────────────────────────────────┐
                  │     Virtual SCPI server (Python)        │
                  │  SourceMeter · DataLogger · Chamber     │
                  └────────────┬────────────────────────────┘
                               │ ctypes  ─────────►  EKF SOC estimator (C++)
                               ▼
                  ┌─────────────────────────────────────────┐
                  │   2nd-order Thévenin cell  (C++)        │
                  │   OCV(SOC) table · Arrhenius(T)         │
                  │   sqrt-cycle aging · fault hooks        │
                  └────────────┬────────────────────────────┘
                               │ per-cycle features
                               ▼
                  ┌─────────────────────────────────────────┐
                  │  StandardScaler → PCA → GMM triage      │
                  │   → mode label · RUL projection         │
                  └─────────────────────────────────────────┘
```

## Layout

```
sprint7_battery_testbench/
├── cpp/                       2nd-order Thévenin cell + EKF + flat C ABI
│   ├── cell_model.{hpp,cpp}
│   ├── ekf_soc.{hpp,cpp}
│   ├── c_api.cpp
│   └── Makefile               -> ../build/libpolaris_bms.{so|dylib}
├── polaris_bms/               Python package
│   ├── native.py              ctypes wrapper
│   ├── instruments.py         TestBench · SourceMeter · DataLogger · VirtualScpiServer
│   ├── profiles.py            HPPC / CC-CV waveforms
│   ├── estimators.py          CoulombCounter · MlAugmentedSoc
│   ├── cycler.py              Accelerated cycling harness + per-cycle features
│   ├── triage.py              StandardScaler -> PCA -> GMM triage + RUL projection
│   └── signals.py             Sensor noise / bias / quantisation
├── tests/                     pytest suites (cell, HPPC, SCPI E2E, estimators)
├── scripts/
│   ├── benchmark_estimators.py
│   ├── run_cycling_campaign.py
│   └── run_all.sh
├── dashboard/app.py           Streamlit: Live bench / SOC / Cycling / Triage
├── reports/                   Written failure analysis reports (portfolio)
└── data/                      Generated CSV/JSON test results
```

## Quickstart

```bash
# 1. Build the C++ core
cd cpp && make && cd ..

# 2. Install Python deps
pip install -r requirements.txt

# 3. Run the full test + characterization pipeline
./scripts/run_all.sh

# 4. Open the dashboard
streamlit run dashboard/app.py
```

## Key results from the bundled data set

| Scenario | CC RMS | EKF RMS | ML-augm. RMS | EKF adv. | ML adv. |
|---|---|---|---|---|---|
| baseline (25 °C, clean sensors) | 0.050 | 0.002 | 0.005 | +97 % | +90 % |
| wrong initial guess (off by 0.4 SOC) | 0.400 | 0.005 | 0.003 | +99 % | +99 % |
| biased current shunt (+80 mA) | 0.076 | 0.011 | 0.011 | +86 % | +86 % |
| biased shunt + bad initial guess | 0.425 | 0.010 | 0.009 | +98 % | +98 % |
| cold soak (−10 °C, biased + bad guess) | 0.213 | 0.055 | 0.055 | +74 % | +74 % |
| hot soak (+45 °C, biased + bad guess) | 0.213 | 0.029 | 0.025 | +87 % | +88 % |
| **mean across 6 scenarios** | | | | **+90 %** | **+89 %** |

The ML residual layer is a small Random-Forest fit on `(V, I, T, EKF_soc)` against the EKF's own residual on a separate held-out simulation. It edges past the bare EKF in the conditions where the EKF has leftover structure (bad guess, hot soak); it adds variance in the baseline where the EKF is already near-optimal. This matches the standard sanity check for a residual learner.

Failure triage (5-class, 60 cycles per scenario, PCA(4) → GMM(8)):

| Class | In-sample accuracy |
|---|---|
| HEALTHY | 98 % |
| LITHIUM_PLATING | 98 % |
| INTERNAL_SHORT | 98 % |
| SEI_GROWTH | 88 % |
| ELECTROLYTE_DEPLETION | 90 % |
| **overall** | **95 %** |

RUL projections (cycles-to-80 %-SoH) for the same scenarios: **Healthy 924, SEI 480, Internal short 467, Electrolyte depletion 368, Li-plating 337** — matching the relative ordering expected from the literature (Li-plating dominates for cold-soak cycling).

## Why this sprint

This sprint closes the three highest-impact gaps in my portfolio against Apple's Battery System Quality Engineer (200668028), Hardware System Validation Engineer (200664001), Hardware Systems Engineer (200659990), and EE Design & Test Engineer (200664207) JDs:

1. **Physics-based battery modeling** (equivalent circuit, gas gauging, SOC/SOH/RUL) — required by Battery QE.
2. **C/C++ in the loop** — Battery QE lists Python and C/C++ as required.
3. **Hardware-style test automation** — pytest framework driving the cell through a SCPI-like instrument interface, identical to what runs on a real lab bench. Required across HSV / HSE / EE Design.

The triage pipeline reuses the **PCA + GMM** anomaly detection from Sprint 3 (Fleet Energy & Battery Risk Studio), extending the previous ML-based SoH work onto a physics-based equivalent-circuit foundation.
