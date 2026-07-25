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
searches an ordered maneuver set and takes the first that restores
`HMD ≥ H_DWC` when re-simulated against the intruder held fixed:

1. **Speed brake** to 65 % ground speed;
2. **Vertical** step of `±V_DWC` (climb/descend one layer) at the vehicle's
   nominal climb rate;
3. **Horizontal offset** — right turn searched over {15, 25, 35, 45, 60}° (right
   turn mirrors the VFR right-of-way convention).

In the live sim, velocity is recovered by finite-difference of position, so each
maneuver is automatically reflected in the next step's conflict prediction.

### 3.1 The recovery envelope (why avoidance can fail)

A resolution is **not free**. The give-way vehicle takes `react_s = 2.5 s` to
detect and commit, and then opens lateral separation at a bounded rate
`lat_rate_ms = 22 m/s` (it cannot teleport sideways). So the separation it can
build by the closest point of approach is roughly

$$\Delta y \;\approx\; \text{lat\_rate}\times\big(t_{\text{CPA}} - t_{\text{react}}\big),\qquad
  t_{\text{CPA}} = \frac{R_{\text{pop-up}}}{v_{\text{closure}}}$$

To recover well clear it needs `Δy ≥ H_DWC = 150 m`, i.e.
`t_CPA ≳ H_DWC/lat_rate + react ≈ 9 s`. A **non-cooperative intruder detected at
short range** ("pop-up") gives a small `t_CPA`, so the maneuver cannot finish in
time and separation is lost. This is the whole point of the tactical demo: it has
a computable **safety envelope**, and the "Inject intruder" control lets you set
the pop-up range and watch it cross from *resolved* to *loss of separation*.

**Outcome classification.** For each injected intruder we track the minimum
achieved separation against its target and label the encounter **loss of
separation** iff horizontal `< 60 m` and vertical `< 15 m` at closest approach
(a genuine near-mid-air-collision-like breach), else **resolved**.

**Verification (§3b).** With a head-on non-cooperative intruder at closure
≈ 110 m/s and seed 7: pop-up at **300 m → loss of separation** (min ≈ 3 m,
`t_CPA` ≈ 3.8 s), **700 m** is borderline-resolved (min ≈ 66 m), **1400 m →
resolved** (min ≈ 173 m). The crossover sits near **600 m** for these dynamics —
move `react_s` or `lat_rate_ms` in `data/airspace.js` and the envelope shifts.

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
altitude layer with no conflict against already-scheduled flights. If nothing
fits within the delay cap, the flight is flagged **unresolved (residual)**.

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

The **capacity knee** is the first fleet size at which the plan can no longer
keep every operation deconflicted within the delay cap (residual > 0). At
seed 42:

| fleet | conflicts | mean delay | residual | throughput |
|---:|---:|---:|---:|---:|
| 10 | 0 | 0.30 min | 0 | 28/h |
| 40 | 3 | 0.81 min | 0 | 80/h |
| 80 | 8 | 2.76 min | 0 | 112/h |
| 100 | 13 | 3.96 min | 1 | 127/h |
| 120 | 29 | 5.47 min | 2 | 148/h |
| 150 | 40 | 7.48 min | 20 | 238/h |

Conflicts grow ~quadratically with fleet size; the network first fails to fully
deconflict around **100–120 simultaneous operations** for this vertiport set and
these thresholds. Change the thresholds in `data/airspace.js` and the knee moves
— which is exactly the sensitivity an operator or vertiport planner cares about.

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

None of these change the qualitative result — that a fixed vertiport network has
a computable operations ceiling — which is the point of the demo.
