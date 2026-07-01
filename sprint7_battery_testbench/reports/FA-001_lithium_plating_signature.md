# Failure Analysis FA-001 — Lithium Plating signature under cold-soak cycling

| | |
|---|---|
| **Report ID** | FA-001 |
| **Cell** | NMC 18650, 3.20 Ah nominal (modelled) |
| **Test bench** | Polaris Virtual Bench VTB-1 (libpolaris_bms 0.1) |
| **Operator** | A. Barbarin |
| **Date** | 2026-06-29 |

## 1. Summary

The cell under test (CUT) was cycled 60 times at a chamber set-point of **−10 °C** (263.15 K) with a 1 C constant-current discharge and a 0.5 C CC-CV charge. The triage pipeline assigned **LITHIUM_PLATING** to 58 / 59 post-baseline cycles with a mean cluster posterior of 0.93. Final state-of-health was **94.33 %**, vs **97.74 %** for the matching healthy cell at 25 °C — a **2.51× acceleration** of the cycle-fade rate (5.67 % loss vs 2.26 %).

All numerical values in this report are computed by `scripts/run_cycling_campaign.py` from the bundled `data/cycle_records.json` dataset; reproducibility instructions are in §5.

## 2. Triage evidence — per-feature separation

Means computed over the trailing 59 cycles of each scenario (the first cycle is dropped because Δ-features are undefined). The deterministic simulation produces tight per-class distributions, so effect sizes (mean difference / healthy std) dominate.

| Feature | Healthy mean | Li-plating mean | Δ (Li − Healthy) | Direction |
|---|---|---|---|---|
| `d_soh_pct` (per-cycle SoH change, %) | −0.033 | −0.084 | **−0.050** | fade rate ~2.5× faster |
| `ir_drop_v` (1 s pulse, V) | 0.0743 | 0.1127 | **+0.0384** | impedance rises (SEI thickening) |
| `rest_relaxation_v` (5 min post-discharge, V) | 0.0888 | 0.1809 | **+0.0921** | larger over-potential to relax |
| `peak_charge_dvdq` (V/Ah, max over charge step) | 84.92 | 56.22 | **−28.70** | dV/dQ peak shifts later & flattens |
| `soh_pct` (run-end value) | 97.74 | 94.33 | **−3.41** | additional capacity loss |

The signatures are consistent with the canonical electrochemical mechanism: at low temperature and during charging, the anode polarisation can drop below 0 V vs Li/Li⁺, causing metallic lithium to plate on the graphite surface. The plated metal is largely electrochemically inactive (irreversible Li loss → capacity fade) and forms additional SEI on its surface (further impedance rise on subsequent cycles).

## 3. RUL projection

Linear regression on the trailing third of the SoH(cycle) trace projects the **80 % SoH crossing at cycle 339** (1000-sample bootstrap of the regression slope: 5th / 95th percentile = **335 / 342**). The bootstrap interval is tight because the simulated stress trajectory is deterministic — any variability comes from the regression sample size, not from cell-to-cell scatter (which the model does not currently represent). On a real bench this interval would be substantially wider.

For comparison, the same projection on the healthy cell crosses 80 % SoH at cycle **924** — a 2.7× longevity advantage.

## 4. Recommended actions

1. **Temperature-derated charge current** below 10 °C — the highest-leverage published mitigation. The model exposes a hook for this in `polaris_bms/profiles.py:cccv_charge`.
2. **Pre-conditioning heater verification** — if production cells include a heater, verify it engages before charging when T_cell < 10 °C.
3. **On-line plating watch** — flag any cell whose `d_soh_pct` exceeds 1.5× a population baseline OR whose `rest_relaxation_v` rises > 50 mV cycle-over-cycle. Both signals appear in our triage feature set.

## 5. Reproduction

```bash
cd cpp && make && cd ..                         # build the C++ core
python3 scripts/run_cycling_campaign.py         # regenerates data/
python3 - <<'PY'
import json
recs = json.load(open('data/cycle_records.json'))
li = [r for r in recs if r['fault']=='LITHIUM_PLATING' and r['cycle']>1]
he = [r for r in recs if r['fault']=='HEALTHY' and r['cycle']>1]
print('Li final SoH', li[-1]['soh_pct'], '%')
print('Healthy final SoH', he[-1]['soh_pct'], '%')
PY
```

## 6. Limitations

- Single-cell, deterministic simulation. No cell-to-cell variability, no full-pack thermal gradient, no measurement-system aging.
- The Li-plating mechanism is implemented as an **R1 impedance multiplier + cycle-fade multiplier + a small charge-voltage offset below 15 °C**, not via a first-principles butler-volmer model. Sign, magnitude, and temperature dependence are calibrated to qualitatively match published data, not to predict absolute kinetics.
- Triage accuracy quoted is **in-sample** (94.6 % overall); no held-out cells were used. Cross-validated accuracy on a held-out cell will be lower; this is appropriate future work.
