# Sprint 11 — UTM Fleet Deconfliction Studio
## Pre-deployment audit, 18 September 2026

Reviewed as a UTM / UAM systems engineer would review it before showing it to an
operator or a vertiport planner. Scope: does the model answer its own question,
do the inputs move the outputs in the direction and magnitude a domain expert
would expect, do the boundary cases hold, and are there discontinuities that are
numerical rather than physical.

**Every finding below was reproduced by execution.** Probe scripts are in
`tools/`, raw console output in `logs/`. No finding is a code-reading inference
unless labelled `INFERENCE`.

Environment: Node v22.23.2, Linux aarch64. `node verify.mjs` passes all 8 of its
own sections before and after this audit; none of the defects below is caught by
the existing verification script.

---

## Verdict

**Do not deploy as it stands.** Three findings are blocking, in the sense that
the tool currently gives an answer a domain reviewer can show to be wrong, on
exactly the two questions the demo exists to answer ("how many operations can
this network absorb" and "when does detect-and-avoid fail").

The underlying engineering is sound: the CPA geometry, the modified-tau
construction, the 4D-intent conflict test and the greedy layer-and-delay planner
are all correct and correctly sourced. The defects are in the metric
definitions, in the coupling between the UI and the integrator, and in the
statistical basis of the headline number — not in the physics.

---

# BLOCKING

## F1 — The animation-speed slider is the physics time step, and it changes the safety verdict

`App.jsx:53` — `const dt = 0.5 * speedMult;` where `speedMult` is the
user-facing "Sim speed" slider, range 1–20, default 6.

The integration step is therefore **0.5 s to 10 s, 3 s by default**, set by a
control the user reasonably believes is a display preference. Everything in the
tactical model is integrated at that step: the 2.5 s reaction latency
(`react_s`), the 22 m/s lateral opening rate, the 16 s maneuver hold, and the
per-step sampling of separation that classifies an encounter.

Measured (`logs/03_timestep_sensitivity.txt`, deterministic target, identical
warm-up, closure 110 m/s):

| pop-up | dt=0.5 s | dt=1 s | **dt=3 s (default)** | dt=5 s | dt=10 s (max) |
|---:|---|---|---|---|---|
| 300 m | LoS 25 m | LoS 30 m | **LoS 30 m** | resolved 250 m | resolved 800 m |
| 500 m | LoS 33 m | LoS 55 m | **resolved 160 m** | LoS 50 m | resolved 600 m |
| 600 m | LoS 55 m | LoS 55 m | **LoS 60 m** | LoS 50 m | resolved 500 m |
| 700 m | resolved 77 m | LoS 59 m | **LoS 40 m** | resolved 150 m | resolved 400 m |
| 900 m | resolved 112 m | resolved 90 m | **resolved 112 m** | resolved 200 m | resolved 200 m |

Three separate defects are visible in that table.

1. **A physically impossible verdict.** At dt ≥ 5 s the 300 m pop-up is reported
   *resolved*, with a minimum separation of 250 m and then 800 m. A head-on
   intruder detected at 300 m with 110 m/s closure gives 2.7 s to CPA against a
   2.5 s reaction latency. Separation cannot be opened. The reported 800 m is
   the signature of sampling tunnelling: the pair is never sampled near each
   other, so the minimum-separation tracker never sees the encounter.
2. **Non-monotonicity in dt.** At 500 m the verdict oscillates LoS → resolved →
   LoS → resolved as the slider moves. Nothing physical changed.
3. **Non-monotonicity in the control the demo is built around.** At dt = 5 s a
   *later* detection (300 m) is reported safer than an earlier one (500 m and
   600 m). This directly inverts the claim in `MODEL.md` §3.1.

Root cause: minimum separation is tracked by per-step sampling
(`sim.js:140-141`) with no sub-step CPA interpolation, and the LoS floor is
60 m while the pair closes 330 m per step at the default setting.

**Fix direction.** Separate the integration step from the display rate: advance
the model at a fixed internal `dt` (0.25–0.5 s) and run N sub-steps per animation
frame, so the slider changes only how fast time is displayed. Independently,
compute the encounter minimum from the analytic CPA between consecutive states
rather than from the sampled positions. Neither change is cosmetic; the second
one is what makes the metric independent of the first.

## F2 — Throughput rises while the network saturates, hiding the capacity limit

`strategic.js:122-125`:

```js
const span = Math.max(1, Math.max(...arrs) - Math.min(...deps));
const throughput = (flights.length / span) * 3600; // "completed ops/hour"
```

The numerator is **total demand**, not accepted operations. Operations the
planner could not deconflict within the delay cap are counted as completed.

Measured (`logs/02_throughput_saturation.txt`, seed 42):

| N | residual | accepted | span (s) | throughput shown |
|---:|---:|---:|---:|---:|
| 135 | 8 | 127 | 2981 | 163 /h |
| 140 | 13 | 127 | 3071 | 164 /h |
| 145 | 15 | **130** | **2269** | **230 /h** |
| 150 | 20 | **130** | **2269** | **238 /h** |
| 155 | 25 | **130** | **2269** | **246 /h** |
| 160 | 30 | **130** | **2269** | **254 /h** |

From N = 145 the network is fully saturated: accepted operations are frozen at
130 and the span no longer moves. The headline metric nevertheless climbs from
230 to 254 ops/h, purely because demand grew. **The capacity metric of a
capacity demo increases monotonically as the network fails.** An operator
reading the chart concludes the network absorbs 254 ops/h when it absorbs 130
operations in a 38-minute span.

The discontinuity at N = 145 (span 3071 → 2269 s, throughput +40 %) is a second
symptom, caused by F4 below.

**Fix direction.** Throughput must be accepted operations over the busy span,
and the chart should carry the accepted-operations curve, which is the quantity
that actually plateaus. The plateau at 130 is the real, defensible answer the
tool is currently hiding.

## F3 — The capacity knee is a single-sample artefact

`MODEL.md` §5 states, as the headline result, that "the network first fails to
fully deconflict around **100–120 simultaneous operations**".

Measured across five demand draws (`logs/06_boundaries_and_seeds.txt`, identical
network, identical thresholds, only the seed changes):

| seed | knee | residual @150 | throughput @150 |
|---:|---:|---:|---:|
| 1 | **80** | 37 | 207 /h |
| 7 | **80** | 28 | 189 /h |
| 42 | **100** | 20 | 238 /h |
| 99 | **120** | 26 | 218 /h |
| 1234 | **150** | 16 | 203 /h |

The knee spans 80 to 150, a factor of 1.9, across random draws of the same
demand process. The published figure is a property of seed 42, not of the
vertiport network. A capacity study presented to a vertiport planner on one
random draw is not a capacity study.

Compounding: the knee is defined as the first entry **in the sweep list** with
residual > 0 (`fleet.js:56`). `verify.mjs` sweeps `[10,20,40,80,120,150]`, which
omits 100, so it reports the knee at 120 while the true first failure at seed 42
is at 100. The headline moves with the granularity of the sweep.

**Fix direction.** Run 20–50 seeds per fleet size, report the median knee with a
band (e.g. 10th–90th percentile), and define the knee by interpolation on
residual > 0 rather than by list membership. This is also a better demo: the band
*is* the uncertainty a planner wants to see.

---

# MAJOR

## F4 — Unresolved flights are charged 900 s of delay they never fly

`strategic.js:105-113`. When no layer/delay combination fits within the cap, the
flight is accepted with `delay_s = maxDelay` (900 s) but its 4D intent is rebuilt
from the **original** departure time:

```js
const intent = buildIntent(f, ref);              // f.dep — no delay applied
placed = { layer: prefLayer, delay_s: maxDelay, intent, resolved: false };
```

So the trajectory flown, the pad occupancy registered (`f.dep + 900`), and the
departure time used in the throughput span all disagree with each other by
15 minutes. Measured (`logs/01_residual_delay.txt`):

- N = 120: 1 800 s of the 39 390 s total delay is phantom (5 %).
- N = 150: **18 000 s of 67 320 s is phantom (27 %)**. Mean delay drops from the
  advertised 7.48 min to 5.48 min once the phantom is removed.

This also propagates into F2: because residual intents arrive early (no delay
applied), `max(arrs)` falls as residuals accumulate, which is the mechanical
cause of the span collapse at N = 145.

**Fix direction.** Decide explicitly what an unresolved operation means. Either
it is rejected (excluded from delay, pad and throughput statistics, counted as
demand not served), or it is accepted at the cap (intent rebuilt at
`f.dep + maxDelay`, and the residual conflict reported). Both are defensible;
the current state is neither.

## F5 — The tactical demo's headline control has a hidden variable, and is not reproducible

`sim.js:183` — `const T = targets[Math.floor(Math.random() * targets.length)];`

The intruder target is drawn with `Math.random`, not the seeded PRNG the rest of
the sprint uses. Two consequences.

**Reproducibility.** The sprint advertises determinism ("seeded ⇒ byte-for-byte
repeatable"). The tactical demo is not: the same seed, same fleet, same pop-up
range gives different outcomes run to run.

**A hidden variable in the advertised control.** Closure speed is
`intruder 55 m/s + target cruise`, and the target cruise ranges from 25 m/s
(VoloCity) to 89 m/s (Joby S4). At a fixed 600 m pop-up
(`logs/04_closure_and_idle_tactical.txt`):

| target drawn | closure | t_CPA | outcome |
|---|---:|---:|---|
| Volocopter VoloCity | 80 m/s | 7.5 s | **resolved**, min 77 m |
| Wisk Gen 6 | 110 m/s | 5.5 s | loss of separation, min 55 m |
| Archer Midnight | 122 m/s | 4.9 s | loss of separation, min 24 m |
| Joby S4 | 144 m/s | 4.2 s | loss of separation, min 24 m |

The user moves no control and gets either verdict. The demo's story — "set the
pop-up range and watch it cross from resolved to loss of separation" — is a
story about time to CPA, and time to CPA is not what the slider sets.

**Fix direction.** Draw the target from the seeded PRNG, and either label the
control in seconds to CPA rather than metres, or display the realised closure
and t_CPA next to the verdict.

## F6 — The resolution turn angle is computed and then discarded

`tactical.js:51-56` searches right turns over {20, 30, 45, 60, 75}° and returns
the first that restores HMD ≥ 150 m, as `{ type: "heading", vel: turned }`.

`sim.js:88` ignores it:

```js
else ag.crossTarget = sep.daa_hmd_m * 1.15;   // fixed 172.5 m lateral offset
```

The selected angle never reaches the simulation; every horizontal resolution
produces the same fixed lateral offset at the same bounded rate. The ordered
search described in `MODEL.md` §3 is, for the horizontal branch, dead
computation in the live sim. (It is still exercised by `verify.mjs` §3, which is
why the test suite does not catch this.)

## F7 — The vertical maneuver escapes the recovery envelope entirely

`tactical.js:59-62`:

```js
const dAlt = give.alt <= keep.alt ? -sep.daa_vert_m : sep.daa_vert_m;
if (Math.abs(give.alt + dAlt - keep.alt) >= sep.daa_vert_m)
  return { type: "vertical", dAlt, vel: give.vel, ok: true };
```

For a same-layer conflict (`give.alt === keep.alt`, the normal case) this
evaluates `|−30| ≥ 30` → always true. The vertical maneuver is granted
unconditionally, with no check against the vehicle's climb rate (2.5–6 m/s) or
against the time remaining to CPA. A 30 m step at 2.5 m/s needs 12 s plus the
2.5 s reaction; the acceptance test asks for neither.

The demo's central pedagogical claim is that a resolution is *not free* and has
a computable envelope. That claim holds for the horizontal branch and not at all
for the vertical one.

---

# MODERATE

## F8 — `MODEL.md` no longer describes the code

Same defect class as the S7/S8 discrepancies found in the S7→S12 integration
campaign, and worth fixing with the same discipline.

| `MODEL.md` says | code does |
|---|---|
| Maneuver order: speed brake → vertical → horizontal (§3, and the header comment of `tactical.js`) | horizontal → vertical → speed brake |
| Turn angles {15, 25, 35, 45, 60}° | {20, 30, 45, 60, 75}° |
| Speed brake to 65 % | 60 % (`tactical.js:66`, `sim.js:86`) |
| §5 capacity table contains a row N = 100 | `verify.mjs` never sweeps 100 |
| §3.1: pop-up 300 m → t_CPA ≈ 3.8 s, min ≈ 3 m | 2.7 s, min 2 m |
| §3.1: pop-up 700 m → min ≈ 66 m ("borderline") | min 127 m |

The maneuver-order reversal is not cosmetic: speed-first and turn-first are
different detect-and-avoid philosophies, and a reviewer from the domain will
read the documented one as the design intent.

## F9 — §3.1 conflates the well-clear threshold with the loss-of-separation floor

The derivation in §3.1 requires `Δy ≥ H_DWC = 150 m`, giving
`t_CPA ≳ 150/22 + 2.5 ≈ 9.3 s`, i.e. a crossover near **1 020 m** at 110 m/s
closure. The crossover actually reported in the same section is **600 m**, which
corresponds to the 60 m LoS floor (`60/22 + 2.5 ≈ 5.2 s → 575 m`). The text
derives one threshold and reports the other as though they were the same
quantity. The arithmetic is right in both cases; the narrative joins them
incorrectly.

## F10 — The tactical layer never fires in the default configuration

Measured over complete runs with no injection
(`logs/04_closure_and_idle_tactical.txt`):

| fleet | predicted tactical conflicts (step-cumulative) | LoS events |
|---:|---:|---:|
| 40 (default) | **0** | 0 |
| 100 | 4 | 0 |
| 150 | 21 | 0 |

At the default fleet size the detect-and-avoid half of the tool is inert for the
entire run. This is not wrong — strategic deconfliction succeeding is precisely
why nothing reaches the tactical layer — but a visitor who does not press
"Inject intruder" never sees the capability the sprint is half about, and the
interface does not say so.

## F11 — Adjacent altitude layers sit exactly on the tactical threshold

`ALT_LAYERS` are spaced 30 m and `daa_vert_m` is 30 m, while the test is
`vert < sep.daa_vert_m` (`tactical.js:33`). Two vehicles on adjacent layers are
at exactly 30 m and are therefore *never* a tactical conflict, by a strict
inequality on a knife edge. Any floating-point drift in altitude during a
vertical maneuver flips the behaviour. Separating the layer spacing from the DAA
vertical threshold (e.g. layers 45 m apart, threshold 30 m) removes the
degeneracy.

## F12 — Maneuver lifecycle: a magic 16 s and no re-tasking

`sim.js:130` sets `t: 16` for every advisory, with no derivation. With
`react_s = 2.5` and `lat_rate_ms = 22`, reaching the 172.5 m offset takes ≈ 10.3 s,
so the offset is held for ≈ 5.7 s before the vehicle starts returning to track —
potentially before CPA for a long-range encounter. Separately, `sim.js:128`
skips any vehicle that already has a maneuver, so a vehicle cannot be re-tasked
for a second, closer intruder while resolving the first.

## F13 — `delayMean_s` is NaN for an empty fleet

`strategic.js:133` divides by `flights.length`. Reachable whenever
`generateFleet` returns zero flights (its guard can trip on a restrictive
vertiport set), not only at N = 0. The UI slider floor of 5 hides it today.

---

# What this audit does not cover

- The React layer, map rendering and responsive behaviour were not reviewed.
- The Dallas–Fort Worth vertiport set was not audited; every measurement above
  is on the Paris network.
- No claim is made about the *correctness of the chosen thresholds*
  (150 m / 30 m / 25 s). They are illustrative by the sprint's own statement and
  that is a defensible position; this audit checks that the model uses them
  consistently, not that they are the right numbers.
- Nothing here is validated against real traffic data. Every number is simulator
  output, as the sprint states.

---

# Fixes applied — 18 September 2026

Implemented in the order the audit ranked them. Each is verified by re-running
the probe that found it; "after" logs carry a `b` suffix or a new number.

| # | Finding | Status |
|---|---|---|
| F1 | Display speed was the integration step | **Fixed** — fixed 0.5 s internal step, sub-stepped; encounter minima from the analytic CPA within each sub-step |
| F2 | Throughput rose as the network saturated | **Fixed** — accepted movements per hour over the departure span; the chart now shows accepted vs requested |
| F3 | Capacity knee was a single-seed artefact | **Fixed** — 30 demand draws, median + 10th–90th band, knee at a 95 % service level by interpolation |
| F4 | Phantom 900 s delay on unresolved flights | **Fixed** — unresolved operations are rejected, not accepted; excluded from delay, pad and throughput |
| F5 | `Math.random` injection, hidden closure variable | **Fixed** — seeded PRNG; realised closure and t_CPA shown with every verdict |
| F6 | Turn angle computed then discarded | **Fixed** — the selected angle sets the lateral opening rate actually flown |
| F7 | Vertical maneuver escaped the envelope | **Fixed** — gated on `climb · (t_CPA − react) ≥ V_DWC` |
| F8 | `MODEL.md` no longer described the code | **Fixed** — §3, §3.1, §4, §5, §6 rewritten against the code; brake is 65 % in both |
| F9 | §3.1 conflated the two thresholds | **Fixed** — both stated in a table, 5.23 s / 575 m for the LoS floor, 9.32 s / 1 025 m to recover well clear |
| F10 | Tactical layer idle at the default fleet | **Disclosed** in §6; not a defect |
| F11 | Layer spacing equals the DAA vertical threshold | **Disclosed** in §6; left as a design choice to revisit |
| F12 | Magic 16 s hold, no re-tasking | **Disclosed** in §6 |
| F13 | `delayMean_s` NaN on an empty fleet | **Fixed** — guarded |

## Evidence that the blockers are gone

**F1.** Identical verdict and identical minimum separation at 0.5, 1, 3, 5 and
10 s per displayed frame, at every pop-up range
(`logs/03b_timestep_after_fix.txt`). The envelope is now monotone in pop-up
range, as the physics requires.

**F1 + F6 + F7, the resulting envelope** (`logs/09_envelope_scan.txt`): loss of
separation at 400–600 m, resolved from 650 m, minimum separation rising 20 m per
100 m of range. The measured crossover (600–650 m) matches the closed form
(575 m), and the slope matches `lat_rate × Δt_CPA` exactly. The tool now fails
where it must and succeeds where it must, and the boundary is computable — which
is what makes it worth showing.

**F2 + F3 + F4** (`logs/08_capacity_band.txt`): capacity ≈ **123 operations,
band 109–131** over 30 demand draws at a 95 % service level, in 0.1 s. Accepted
operations rise 40 → 80 → 99 → 115 → 126 → 135 as demand goes 40 → 160: the
curve leaves the diagonal progressively instead of a metric that climbed while
the network failed.

## Not fixed, deliberately

F11's layer/threshold degeneracy is a modelling choice, not an error, and
changing it moves every published capacity number; it is disclosed and left for
a decision. F12's 16 s hold and the absence of re-tasking are real limitations
of a demonstrator and are now stated rather than silent.

## Still outstanding

- The Dallas–Fort Worth network has not been audited; every measurement here is
  Paris.
- `verify.mjs` still passes all 8 sections but was written before these
  findings: it does not yet assert step-independence, the acceptance-rate
  definition, or the envelope crossover. Those assertions should be added so the
  suite would catch a regression on any of them.
- The basemap was switched from CARTO (which now requires an API key and
  rendered a watermark across the map) to OpenStreetMap tiles with a CSS dark
  filter. OSM's tile policy targets low-volume use; a real deployment needs a
  paid provider.

---

# Addendum — 21 September 2026

Raised by visual review of the running tool, after the fixes above.

## F14 — The headline separation tile measured the wrong quantity

The "MIN SEP" tile showed the minimum 3-D **slant** range. Its floor is the
deliberate altitude-layer spacing, so it sat at ~30 m in normal operation and
was permanently coloured as an alarm, while the quantity a controller watches —
lateral separation — was never displayed.

Measured over a full run with no injection (`tools/p10_minsep_decomposition.mjs`):

| fleet | tile showed | which decomposed as | true minimum horizontal |
|---:|---:|---|---:|
| 40 | 31 m | 21 m horizontal + 30 m vertical | **4 m** |
| 100 | 30 m | 2 m horizontal + 30 m vertical | **0 m** |

**Fixed.** The tile now reports minimum horizontal separation with the vertical
gap at that instant, and only raises the alarm state when both the horizontal
and vertical loss-of-separation floors are breached.

## F11 upgraded — layer spacing decoupled from the DAA vertical threshold

F11 was graded *moderate, disclosed* above. The measurement behind F14 shows it
is more consequential than that grading. With `V_strat = V_DWC = 30 m` and a
strict `<` in the tactical test, adjacent-layer traffic could never raise a
conflict — and at 150 operations **90 distinct pairs overfly each other within
60 m horizontally**, some at 0 m, with nothing between them but that 30 m band
and no part of the model watching it.

**Fixed.** `V_strat` is now 45 m (layers at 300/345/390/435/480/525 m) while
`V_DWC` stays 30 m. Correctly-flown adjacent-layer traffic remains outside the
DAA threshold; an aircraft more than 15 m off its assigned altitude is now seen.

The change is free: layer spacing does not enter strategic deconfliction, which
compares layer identity rather than distance. Re-measured after the change —
capacity **123 operations, band 109–131**, and the tactical envelope crossover
still between 600 and 650 m, both identical to before.

Remaining and disclosed: the model still has no altitude-keeping error, so the
15 m margin is nominal. A layered-corridor design of this kind would in practice
be justified against an altimetry error budget, which is out of scope here.
