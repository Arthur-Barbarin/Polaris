# Model specification

Companion to the README — written to be reviewed by a UTM / UAM systems
engineer. Every formula and constant is sourced or derived, and every number is
reproduced by `node verify.mjs`.

---

## 0. Reference frames

Conflict math is done in a local **East-North-Up (ENU)** frame in metres,
obtained by an equirectangular projection about a reference point (Paris centre,
48.8566 °N, 2.3522 °E):

$$x = (\lambda - \lambda_0)\cdot\frac{\pi}{180}\,R\cos\phi_0,\qquad
  y = (\phi - \phi_0)\cdot\frac{\pi}{180}\,R$$

with `R = 6 371 008.8 m` (IUGG mean radius). Over the Paris metro area (< ~60 km)
equirectangular distortion is < 0.3 %, negligible against the 150–300 m
separation buffers. Distances between named sites use the exact haversine.

---

## 1. Closest point of approach (CPA)

For two vehicles at ENU positions `p₁, p₂` moving at constant velocities
`v₁, v₂`, define relative position `r = p₁ − p₂` and relative velocity
`v = v₁ − v₂`. The time of closest approach is

$$t^\* = \max\!\left(0,\; -\frac{r\cdot v}{v\cdot v}\right)$$

(clamped to 0 because a CPA in the past means the pair is now diverging), and the
**horizontal miss distance** is `HMD = |r + v\,t^\*|`. The pair is *closing* iff
`r·v < 0`.

**Verification (`verify.mjs` §1):** head-on (2 km apart, 50 m/s each) →
`t\* = 20 s`, `HMD = 0`; 90° crossing → `t\* = 50 s`, `HMD ≈ 0`; parallel offset
tracks → `HMD = offset`, `closing = false`. All match closed form.

---

## 2. DAA well clear (tactical)

We use the RTCA **DO-365 (SC-228)** well-clear construction. The **modified tau**
with distance modification `DMOD` is

$$\tau_{\text{mod}} = \frac{DMOD^2 - r^2}{r\,\dot r},\qquad \dot r = \frac{r\cdot v}{|r|}$$

defined when closing (`ṙ < 0`), else `+∞`. A **well-clear violation** is predicted
when, at CPA, all three hold while closing:

$$\text{HMD} < H_{\text{DWC}},\quad |\Delta z| < V_{\text{DWC}},\quad \tau_{\text{mod}} < \tau_{\text{DWC}}$$

**Thresholds used (illustrative, editable in `data/airspace.js`):**

| symbol | value here | DO-365 value for large UAS | why smaller |
|---|---|---|---|
| `H_DWC` | 150 m | 4000 ft ≈ 1219 m | urban eVTOL cruise ~25–90 m/s vs ~100+ m/s jets/turboprops |
| `V_DWC` | 30 m | 450 ft ≈ 137 m | tight vertical layering in low-altitude corridors |
| `τ_DWC` | 25 s | 35 s | shorter closing geometries at lower speeds |

A hard **loss-of-separation (LoS)** floor (60 m horizontal / 15 m vertical) flags
genuine near-misses that a resolution failed to prevent.

> This is a **simplified geometric** well-clear test. It is *not* ACAS-Xu /
> DO-386 (a trained/optimised lookup-table resolution logic), which is not
> claimed here.

**Verification (§2–3):** `τ_mod = 19.89 s` for the closed-form head-on case;
`+∞` when opening; head-on same-layer pair flags a violation and yields a valid
resolution; a pair separated by `V_DWC + 5 m` does not.

---

## 3. Tactical resolution

On a predicted violation the **give-way** vehicle (the non-cooperative intruder
never maneuvers; otherwise the later-departing / lower-priority flight yields)
searches an ordered maneuver set, least intrusive first, and takes the first
that both restores `HMD ≥ H_DWC` against the intruder held fixed **and can
physically be completed before CPA**:

1. **Horizontal offset** — smallest right turn over {20, 30, 45, 60, 75}° that
   works (right turn mirrors the VFR right-of-way convention). The selected
   angle sets the lateral opening rate actually flown,
   `min(lat_rate, v·sin θ)`, so a gentle turn genuinely takes longer to build
   separation than a hard one. A turn is only offered if
   `lat_rate_eff · (t_CPA − react) ≥ 1.15·H_DWC`.
2. **Vertical** step of `±V_DWC` (climb/descend one layer) — offered only if the
   vehicle's climb rate can build `V_DWC` in the time left,
   `climb · (t_CPA − react) ≥ V_DWC`. Climb rates are 2.5–6 m/s, so a 30 m step
   needs 5–12 s plus the reaction: this branch is genuinely unavailable in a
   late encounter.
3. **Speed brake** to 65 % ground speed, as a last resort.

If nothing in the set can recover in the time available the vehicle flies the
hardest turn anyway and the encounter is scored for what it is. In the live sim,
velocity is recovered by finite-difference of position, so each maneuver is
automatically reflected in the next step's conflict prediction.

> **Integration step.** The model is integrated at a **fixed 0.5 s** step
> regardless of the display rate. This matters: when the animation-speed control
> was the integrator step, a pair closing at 110 m/s advanced 330 m between
> samples, passed straight through the 60 m loss-of-separation floor unsampled,
> and was scored *resolved*. Encounter minima are additionally taken from the
> analytic CPA **within** each sub-step rather than from its endpoints, so the
> verdict is independent of the step. Verified: identical verdicts and identical
> minimum separations at 0.5, 1, 3, 5 and 10 s per displayed frame
> (`audit_2026-09/logs/03_timestep_sensitivity.txt`).

### 3.1 The recovery envelope (why avoidance can fail)

A resolution is **not free**. The give-way vehicle takes `react_s = 2.5 s` to
detect and commit, and then opens lateral separation at a bounded rate
`lat_rate_ms = 22 m/s` (it cannot teleport sideways). So the separation it can
build by the closest point of approach is roughly

$$\Delta y \;\approx\; \text{lat\_rate}\times\big(t_{\text{CPA}} - t_{\text{react}}\big),\qquad
  t_{\text{CPA}} = \frac{R_{\text{pop-up}}}{v_{\text{closure}}}$$

There are **two** thresholds here and they are not the same number.

| to achieve | needs `Δy ≥` | `t_CPA ≳ Δy/lat_rate + react` | at 110 m/s closure |
|---|---:|---:|---:|
| avoid a **loss of separation** (the 60 m floor) | 60 m | **5.23 s** | **≈ 575 m** |
| fully **recover well clear** (`H_DWC`) | 150 m | **9.32 s** | ≈ 1 025 m |

A **non-cooperative intruder detected at short range** ("pop-up") gives a small
`t_CPA`, so the maneuver cannot finish in time and separation is lost. This is
the whole point of the tactical demo: it has a computable **safety envelope**,
and the "Inject intruder" control lets you set the pop-up range and watch it
cross from *resolved* to *loss of separation*.

Because the closure speed depends on which cooperative vehicle the intruder is
set against (80 m/s against a VoloCity, 144 m/s against a Joby S4), the pop-up
range alone does not determine the outcome. The realised closure and `t_CPA` are
therefore displayed next to every verdict, and the target is drawn from the
scenario's seeded PRNG so an encounter is reproducible.

**Outcome classification.** For each injected intruder we track the minimum
achieved separation against its target and label the encounter **loss of
separation** iff horizontal `< 60 m` and vertical `< 15 m` at closest approach
(a genuine near-mid-air-collision-like breach), else **resolved**.

**Verification (§3b and `audit_2026-09/logs/09_envelope_scan.txt`).** Head-on
non-cooperative intruder, closure 110 m/s, seeded target:

| pop-up | `t_CPA` | outcome | min sep |
|---:|---:|---|---:|
| 400 m | 3.6 s | loss of separation | 14 m |
| 500 m | 4.5 s | loss of separation | 33 m |
| 600 m | 5.5 s | loss of separation | 53 m |
| **650 m** | **5.9 s** | **resolved** | **63 m** |
| 800 m | 7.3 s | resolved | 92 m |
| 1 000 m | 9.1 s | resolved | 131 m |

The measured crossover sits between **600 and 650 m**, against the closed-form
575 m from the table above, and the minimum separation grows by 20 m per 100 m
of pop-up range — exactly `lat_rate × Δt_CPA = 22 × (100/110)`. Model and closed
form agree. Move `react_s` or `lat_rate_ms` in `data/airspace.js` and the
envelope shifts accordingly.

---

## 4. Strategic deconfliction (pre-departure)

Each flight is a 4D **operational intent**: a straight cruise leg from origin to
destination vertiport at cruise speed `v_c`, giving duration `d/v_c`, on one of
six altitude layers spaced by `V_strat = 30 m`. Position along the leg is
`p(t) = a + \hat d\,v_c(t - t_{dep})` for `t ∈ [t_dep, t_arr]`.

**Same-layer conflict:** two intents conflict iff their airborne windows overlap
and the minimum horizontal separation over the overlap is `< H_strat = 300 m`.
Because both move at constant velocity within the overlap window `[t₀, t₁]`, the
minimum is closed-form (§1 clamped to the window). Different layers are
vertically separated (`≥ V_strat`) throughout cruise.

**Resolution — greedy, in departure order.** For each flight try, in increasing
departure delay (30 s steps, 15 min cap): first check the **origin pad is free**
(no other accepted departure within `T_pad = 90 s`); then place it on the first
altitude layer with no conflict against already-scheduled flights.

**If nothing fits within the delay cap the operation is REJECTED**, not
accepted-with-a-caveat. A USS would not authorise the intent. A rejected
operation holds no layer and no pad and is excluded from the delay,
pad-occupancy and throughput statistics: it is demand the network did not serve,
and that is the quantity the capacity chart shows. (Previously such a flight was
accepted on its preferred layer, charged the full 900 s cap in the delay
statistics while its 4D intent was rebuilt at the *original* departure time —
27 % of the reported mean delay at 150 operations was delay no aircraft flew.)

**Throughput** is accepted **movements per hour over the departure span**, the
unit a network or vertiport planner uses. It is deliberately not measured from
first departure to last arrival: that span is set by the single longest route,
so one flight crossing between accepted and rejected moved the headline by 38 %
with no change in what the network served.

$$H_{\text{strat}} = 300\text{ m},\quad V_{\text{strat}} = 30\text{ m},\quad T_{\text{pad}} = 90\text{ s}$$

**Sources / rationale.** The 4D-intent, pre-departure conflict-detection design
follows the **FAA UTM ConOps v2.0** and **ASTM F3548-21** (USS strategic
conflict detection over operational intents). **Vertiport pad throughput** as the
binding network constraint is the recurring finding of NASA UAM, EASA UAM, and
Uber Elevate capacity work; 90 s is a mid-range launch/recovery pad-occupancy
value from that literature. All values are illustrative and editable.

**Verification (§4–5, 7):** head-on corridor intents converge to `minSep ≈ 0`;
non-overlapping departures give `minSep = ∞`; layers are exactly `V_strat` apart;
at seed 42 / 40 ops the plan drives post-plan same-layer conflicts to 0; repeat
runs are byte-identical (determinism).

---

## 5. Capacity scaling — the headline

Fleets are generated with a seeded PRNG (mulberry32): random origin/destination
vertiport pairs (hops > 45 km rejected as outside urban eVTOL range), random
vehicle types, and departures spread over a 10-minute demand window. For each
fleet size the strategic planner runs and we record baseline conflicts, mean
delay, residual (unresolved) operations, and throughput.

**Capacity is stated at a service level, over many demand draws.** The knee is
the demand at which the planner can no longer accept **95 %** of the requested
operations, obtained by interpolation between sweep points — not "the first
entry in the sweep list with at least one rejection", which rested on a single
flight and moved with the granularity of the list (omitting 100 from the list
moved the published knee from 100 to 120).

Capacity is a property of the network **and of the demand profile**. A single
random draw is not a capacity study: under the old single-seed definition this
network's knee was 80, 80, 100, 120 and 150 for seeds 1, 7, 42, 99 and 1234, a
factor of 1.9. The tool therefore runs **30 independent demand draws** and
reports a median with a 10th–90th percentile band (0.1 s for the whole sweep, so
it recomputes live).

Paris network, 30 seeds, 95 % service level:

| requested | accepted p10 / median / p90 | mean delay p10 / median / p90 (min) |
|---:|---:|---:|
| 40 | 40 / 40 / 40 | 0.74 / 1.03 / 1.63 |
| 80 | 79 / 80 / 80 | 2.89 / 3.30 / 3.67 |
| 100 | 97 / 99 / 100 | 4.11 / 4.56 / 4.86 |
| 120 | 111 / 115 / 117 | 5.35 / 5.63 / 5.94 |
| 140 | 123 / 126 / 130 | 6.23 / 6.52 / 6.78 |
| 160 | 130 / 135 / 140 | 6.95 / 7.20 / 7.48 |

**Capacity ≈ 123 simultaneous operations, band 109–131** (all 30 draws reach the
threshold). The accepted curve leaves the "everything served" diagonal
progressively rather than at a cliff, which is the honest shape: acceptance
degrades, it does not collapse. Change the thresholds in `data/airspace.js` and
the band moves — which is exactly the sensitivity an operator or vertiport
planner cares about, and the band is what should be quoted, not the point.

**Vehicle cruise speeds** (manufacturer-published nominal, rounded): Volocopter
VoloCity 25 m/s, Wisk Gen 6 55 m/s, Archer Midnight / Vertical VX4 67 m/s, Joby
S4 89 m/s. Climb rates are order-of-magnitude assumptions (2.5–6 m/s), used only
to time vertical resolution maneuvers.

---

## 6. Known simplifications (disclosed)

- Straight-line cruise legs; no wind, no turn dynamics, no fuel/energy state
  (energy is covered by Sprints 3, 5, 6, 7).
- Strategic layer deconflicts cruise only; climb/descent transitions are left to
  the tactical layer.
- Pad model constrains **origin departure** occupancy; destination arrival-pad
  and airspace-fix merging are not yet modelled.
- Geometric tactical resolution, not a certified sense-and-avoid logic.
- A vehicle already flying a resolution is not re-tasked for a second intruder,
  and a resolution is held for a fixed 16 s before the vehicle returns to track.
- Altitude layers are spaced exactly `V_strat = V_DWC = 30 m` and the tactical
  vertical test is a strict `<`, so adjacent layers are never a tactical
  conflict. This is deliberate for cruise but it is a knife edge; separating the
  layer spacing from the DAA threshold would remove the degeneracy.
- At the default fleet of 40 the strategic plan is good enough that the tactical
  layer never fires on its own over a whole run. Use "Inject intruder" to
  exercise it; that is what the control is for.

None of these change the qualitative result — that a fixed vertiport network has
a computable operations ceiling — which is the point of the demo.
