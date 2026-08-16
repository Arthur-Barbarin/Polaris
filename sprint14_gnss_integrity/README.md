# Sprint 14 — GNSS Integrity Monitor

**Stack:** Python · NumPy · pytest

A navigation-**integrity** monitor for a GNSS receiver: it runs RAIM (Receiver
Autonomous Integrity Monitoring) fault detection and exclusion, computes the
protection level that decides whether a fix may be trusted, and adds a
spoofing/jamming screen that catches the coordinated attack RAIM is blind to —
then measures all of it over a seeded Monte-Carlo threat field.

> Answers: *"Can this position fix be trusted right now — is a satellite
> faulted, is the signal jammed, is it being spoofed — and across a field of
> attacks, how often does the receiver hand over Hazardously Misleading
> Information with RAIM alone versus with the full monitor?"*

This is a new domain for the portfolio — **sensor integrity and security**,
rather than vehicle dynamics or mission planning — and it pairs a classical
estimation-theory core (least squares, chi-square residual tests, protection
levels) with a security angle (spoof/jam detection) that vehicle-autonomy teams
increasingly have to own.

---

## The two things a visitor should try

1. **Screen a single spoofing attack.**
   ```bash
   python scripts/run_gnss.py single --scenario spoof
   ```
   A coordinated spoof drags the fix **~190 m** off truth. RAIM checks its
   residual (`SSE/σ² ≈ 4` vs a threshold of `18`) and reports **no fault** — it
   would hand the spoofed position straight to the flight computer. The added
   screen sees an unnaturally flat, high C/N0 profile and a large position
   innovation and **rejects the fix**. Try `--scenario fault` to watch RAIM do
   its classic job well: detect the biased satellite and exclude it.

2. **Run the Monte-Carlo threat campaign.**
   ```bash
   python scripts/run_gnss.py campaign --n 2000 --seed 14
   ```
   2000 scenarios in each of four families. Nominal: false-alarm rate **0.0015**
   (matching the `1e-3` design) and **99.5%** availability. Single fault: **97.7%**
   detected, **99.3%** excluded correctly, horizontal error cut **25 m → 4.5 m**.
   Jamming: **100%** detected. And the headline — **spoofing**:

   | | RAIM only | Full monitor |
   |---|---|---|
   | detection rate | **0.2%** | **100%** |
   | Hazardously Misleading Information events | **26** | **0** |

---

## What's modelled (and the honesty notes)

**The estimator and RAIM are the textbook ones.** The linearized GNSS
observation is `z = H·Δx + ε` with `H` the geometry matrix and `ε ~ N(0, σ²)`.
The residual (parity) vector's sum of squares is chi-square with `n − 4` degrees
of freedom under the null, so the detection threshold is a chi-square quantile
of the false-alarm probability, and the Horizontal Protection Level is
`slope_max · σ · pbias` with `pbias` from the non-central chi-square. Those
statistics are implemented from a hand-rolled incomplete-gamma (`gnss/chi2.py`)
and **pinned to published quantiles** in the tests — no SciPy dependency.

**Coordinated spoofing is blind to RAIM by construction, and the model is
honest about it.** The spoof scenario adds `H·Δx_spoof` to *every* pseudorange,
so the solution moves while the residual stays noise-sized. RAIM cannot see it
(0.2% detection — essentially the false-alarm floor). The value of the added
C/N0 + position-innovation screen is therefore the collapse in **Hazardously
Misleading Information** events (fix trusted while the error exceeds the alert
limit): **26 → 0** over the campaign. That is the integrity analogue of a risk
ratio, and it is the whole point of the sprint.

**Availability is a property of geometry, decided before trusting the fix.**
HPL vs HAL is computed from `H` alone; a fix with HPL ≥ HAL is declared
*unavailable* rather than used. This is the standard separation between "is the
geometry strong enough to protect me" and "does the data look faulted".

**Single-epoch snapshot RAIM.** No carrier phase, no multi-epoch filtering, no
receiver clock model beyond the estimated bias. The independent position prior
that powers the spoof-innovation test stands in for a previous epoch or an
inertial estimate. These are clean extensions, not hidden assumptions.

**No real signals** — as in Sprints 7–13, every measurement is synthetic,
generated from seeded geometry and noise, and byte-for-byte reproducible.

---

## Architecture (one paragraph; full detail in `MODEL.md`)

Five small, independently testable layers. `chi2.py` provides the chi-square and
non-central chi-square functions the thresholds are built on. `constellation.py`
turns satellite azimuth/elevation into the geometry matrix and DOP.
`measurements.py` builds the linearized measurement and the four seeded threat
scenarios. `raim.py` is the least-squares solve, the residual detection test,
fault exclusion, and the protection level. `spoofing.py` adds the two detectors
RAIM lacks — a C/N0 signature test and a position-innovation (Mahalanobis) test.
`metrics.py` runs the whole threat field and rolls it up.

```
gnss/
  chi2.py          # incomplete-gamma; chi2 + non-central chi2 (no SciPy)
  constellation.py # satellite LOS, geometry matrix, DOP
  measurements.py  # linearized pseudoranges + seeded fault/spoof/jam scenarios
  raim.py          # LS solve, residual detection, exclusion, protection level
  spoofing.py      # C/N0 + position-innovation spoof/jam screen
  metrics.py       # Monte-Carlo threat campaign roll-up
scripts/
  run_gnss.py      # CLI: single scenario, or a campaign
  report.py        # markdown integrity report
  verify.py        # reproduces every headline number below
tests/             # 27 tests: stats quantiles, geometry, RAIM, spoof, campaign
reports/           # sample integrity report
```

---

## Reproduce every number

```bash
python scripts/verify.py     # deterministic, no network/SciPy, exits non-zero on drift
python -m pytest -q          # 27 tests
```

`verify.py` pins the chi-square helper to published quantiles and asserts each
campaign headline:

- **stats:** `chi2_ppf(0.95,1)=3.8415`, `chi2_ppf(0.99,4)=13.277`, non-central
  reduces to central at `λ=0`.
- **nominal:** false-alarm rate 0.0015 (design 1e-3), availability 99.5%.
- **single fault:** 97.7% detected, 99.3% excluded correctly, error 25.3 → 4.5 m.
- **spoof (headline):** RAIM-only detection 0.2%, full-monitor detection 100%,
  Hazardously Misleading Information events **26 → 0**.
- **jamming:** 100% detected.
- **reproducibility:** campaign identical across independent runs.

See `reports/integrity_report.md` for a full sample report.

---

*Engineering clarity for complex futures.*
