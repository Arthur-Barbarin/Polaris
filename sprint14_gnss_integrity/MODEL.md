# MODEL.md — GNSS Integrity Monitor: estimation, statistics, and design choices

This document explains *what* is modelled and *why*. The through-line: an
integrity monitor is only as trustworthy as the statistics behind its
thresholds and the honesty of the threat model it is measured against. Both are
kept auditable here.

## 1. The measurement model

Everything is the **linearized snapshot GNSS** model in a local ENU frame:

```
z = H · Δx + ε ,   ε ~ N(0, σ² I)
```

- `Δx = [East, North, Up, clock]` is the 4-vector the receiver solves for.
- `H` (n×4) is the geometry matrix: each row is the negative unit
  line-of-sight to a satellite plus a 1 for the receiver clock.
- `σ` is the user range accuracy (URA), the 1-σ pseudorange noise.
- Truth is `Δx = 0`; a healthy receiver sees only `ε`.

Snapshot (single-epoch) is a deliberate scope: it is the regime in which RAIM
and protection levels are classically defined, so nothing about the integrity
mathematics is hidden behind a filter.

## 2. The statistics, from scratch (`chi2.py`)

RAIM needs exactly three statistical quantities, and pulling in SciPy for them
would be a deployment liability, so they are built on a hand-rolled
**regularized incomplete gamma** (series + continued fraction, the standard
Numerical-Recipes split):

- **chi-square CDF/quantile** — the detection threshold is `σ²·χ²⁻¹(1−P_fa; n−4)`.
- **non-central chi-square CDF** — a Poisson-weighted mixture of central
  chi-squares.
- **pbias** — the non-centrality `√λ` solving `F_ncx2(threshold; n−4, λ) = P_md`;
  the bias size, in σ units, that is just caught at the required
  missed-detection probability.

The unit tests pin these to published values (`χ²⁻¹(0.95,1)=3.8415`,
`χ²⁻¹(0.99,4)=13.277`, …), so the whole tower of thresholds rests on numbers
anyone can check against a table.

## 3. Geometry and DOP (`constellation.py`)

Satellites are described by azimuth and elevation — the only thing that matters
for the linearized solution. The unit line-of-sight is
`(cos el·sin az, cos el·cos az, sin el)`; the geometry matrix row is its
negative plus a clock 1. Dilution-of-precision values are the square roots of
the diagonal of `(HᵀH)⁻¹`, in the state order E/N/U/clock. More satellites and a
better spread lower the DOP — the tests assert exactly that.

## 4. RAIM: detection, exclusion, protection (`raim.py`)

**Detection.** The least-squares solution is `Δx̂ = (HᵀH)⁻¹Hᵀz`; the residual
(parity) vector is `w = (I − P)z` with `P = H(HᵀH)⁻¹Hᵀ`. Under the null,
`wᵀw/σ² ~ χ²(n−4)`. Detect when it exceeds `χ²⁻¹(1−P_fa; n−4)`. Because that is
the *definition* of the false-alarm rate, the empirical nominal false-alarm rate
lands on `P_fa` (0.0015 vs 1e-3 over the campaign) — a built-in sanity check.

**Exclusion.** When a fault is detected, drop each satellite in turn and
re-solve; removing the faulted satellite is what collapses the residual, so the
excluded satellite is the one whose leave-one-out solution has the smallest SSE.
The tests confirm the injected satellite is the one removed ~99% of the time and
that exclusion cuts the horizontal error (25 → 4.5 m).

**Protection level.** For each satellite the horizontal **slope** relates an
undetectable bias to horizontal position error:
`slope_i = √((A₀ᵢ² + A₁ᵢ²)/(I−P)ᵢᵢ)` with `A = (HᵀH)⁻¹Hᵀ`. The Horizontal
Protection Level is `HPL = slope_max · σ · pbias`. HPL is compared to the
operation's Horizontal Alert Limit (HAL); `HPL ≥ HAL` means the geometry cannot
guarantee integrity and the fix is declared **unavailable**. This decision uses
`H` only — no measurement — which is the correct separation between "is my
geometry strong enough" and "does my data look faulted".

## 5. Why RAIM is not enough — the spoof model (`measurements.py`, `spoofing.py`)

RAIM watches one thing: the residual. A **coordinated spoof** defeats it by
construction — add `H·Δx_spoof` to every pseudorange and the solution moves by
`Δx_spoof` while the residual stays pure noise. In the campaign RAIM detects
0.2% of spoofs (the false-alarm floor). So the monitor adds two detectors that
look at information RAIM ignores:

- **C/N0 signature.** One spoofing transmitter drives every tracked signal to a
  similar, high carrier-to-noise ratio. Genuine satellites show an
  elevation-dependent *spread*; a flat, high C/N0 profile
  (`mean > 48 dB-Hz AND std < 1.2`) is anomalous.
- **Position innovation.** The spoofed solution jumps relative to an independent
  position prior (previous epoch or inertial). The squared Mahalanobis distance
  `d² = δᵀ(Q_sol + Q_prior)⁻¹δ` is `χ²(2)` under the null; a large `d²` flags a
  discontinuity honest geometry never produces.

A fix is trusted only if **nothing** trips — RAIM, jamming, or either spoof
test. The measured benefit is the collapse of **Hazardously Misleading
Information** (error beyond HAL while the fix is reported usable) from 26 events
to 0 across the campaign.

## 6. The metrics that matter (`metrics.py`)

Four threat families, each scored the way an integrity requirement is written:

- **nominal** → false-alarm rate and availability;
- **single fault** → detection, correct-exclusion, error before/after FDE, and
  any HMI;
- **spoof** → detection by RAIM alone vs the full monitor, and HMI counts both
  ways (the headline);
- **jamming** → detection from the C/N0 floor.

The spoof row is the integrity analogue of Sprint 13's collision risk ratio:
the same field of hazards, scored with the safeguard off and on, and the
benefit reported as the reduction in the events that actually hurt.

## 7. What this is not

- Not multi-epoch: no carrier phase, no time filtering, no clock dynamics. The
  position prior stands in for temporal information.
- Not a multi-fault ARAIM: one fault per single-fault scenario; the spoof is a
  single coordinated attacker.
- Not a receiver front-end model: jamming is represented by depressed C/N0 and
  inflated noise, not by correlator-level effects.

Each is a clean extension the layering already supports — a temporal filter in
`measurements.py`, a multi-fault subset search in `raim.py`, more detectors in
`spoofing.py` — without disturbing the statistical core in `chi2.py`, which is
the part that has to stay faithful.

*Engineering clarity for complex futures.*
