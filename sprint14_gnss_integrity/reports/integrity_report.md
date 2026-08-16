# GNSS Integrity Monitor — Campaign Report

Monte-Carlo threat field: **2000 scenarios per family**, seed `14`. Configuration: false-alarm probability `1e-03`, missed-detection probability `1e-03`, Horizontal Alert Limit `200 m`, pseudorange noise `5.0 m` (1σ).

Each scenario is a single measurement epoch; the linearized GNSS solution, RAIM residual test, fault exclusion, protection level, and spoof/jam screen are all computed from the same geometry.

## Nominal (fault-free)

| Metric | Value |
|---|---|
| False-alarm rate (full screen) | 0.0015 |
| False-alarm rate (RAIM only) | 0.0015 |
| Availability (HPL < HAL) | 0.995 |
| Median HPL | 37 m |

The empirical false-alarm rate tracks the configured `1e-03` — the chi-square threshold is doing exactly what it was sized to do.

## Single fault (step bias on one satellite)

| Metric | Value |
|---|---|
| Detection rate | 0.977 |
| Correct-exclusion rate | 0.993 |
| Horizontal error before FDE | 25.3 m |
| Horizontal error after FDE | 4.5 m |
| HMI events (undetected, error > HAL) | 0 |

This is the classic RAIM job, and RAIM does it well: the residual test catches the biased satellite and exclusion restores the fix.

## Spoof (coordinated, residual-clean) — headline

A spoofer shifts every pseudorange by a self-consistent amount, moving the solution while leaving the residual noise-sized. Residual RAIM is blind to it *by construction*; the added C/N0 and position-innovation screen is what restores integrity.

| Metric | RAIM only | Full monitor |
|---|---|---|
| Detection rate | 0.002 | 1.000 |
| HMI events (error > HAL, fix trusted) | 26 | 0 |

- **Hazardously-misleading-information events collapse 26 → 0 (ratio 0.000).** This is the value of the added screen, stated the way an integrity case must be.

## Jamming (depressed C/N0)

Detection rate from the C/N0 floor: **1.000**.

## Honesty notes

- Single-epoch, **snapshot** RAIM — no carrier-phase, no time filtering, no multi-epoch consistency. The position prior for the spoof innovation test stands in for a previous epoch or an inertial estimate.
- The spoof model is a **fully coordinated** bias (the hardest case for residual RAIM). Partial or clumsy spoofing would be *easier* to catch, so these detection numbers are a conservative floor for the monitor and a conservative ceiling for RAIM-alone.
- All measurements are **synthetic**, generated from seeded geometry and noise; the campaign is byte-for-byte reproducible.
- Every figure is a residual, a distance, or a count — no learned or hand-tuned scores.

*Engineering clarity for complex futures.*
