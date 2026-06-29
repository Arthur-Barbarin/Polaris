# Model specification

Companion to the README — written to be reviewed by an aerospace / drone-ops engineer.
Every formula and constant is sourced or derived.

---

## 1. Energy model

### 1.1 Derivation

For each catalogued drone we accept the manufacturer's quoted endurance as the strongest empirical anchor (a real flight on a known battery, measured at calm wind, no payload, sea level — i.e. their best case). Average mission power is then:

$$\bar{P} = \frac{E_{\text{batt}} \cdot \eta_{\text{usable}}}{t_{\max}}$$

with `η_usable = 0.85` (15% reserve, baseline industry practice; FAA BVLOS waivers typically demand 20–25%, which the operator can apply by reading the displayed margin).

For the Skydio X10 (156.17 Wh, 40 min) this yields `P̄ ≈ 199 W` over a 2.49 kg airframe — `80 W/kg`. For the DJI M30 (263.2 Wh, 41 min) it yields `P̄ ≈ 327 W` over 3.77 kg — `87 W/kg`. Both lie within the empirical 80–100 W/kg band reported for comparable industrial multirotors (e.g. DJI Mavic 3 at ≈ 95 W/kg).

### 1.2 Mission energy

We treat cruise and hover power as equal to P̄. This is **honest if disclosed**: in practice forward flight power dips slightly below hover (induced power decreases up to ~30 m/s for typical quadrotors before profile drag dominates), and hover is somewhat above. The approximation is good to within ±10% for missions under 30 minutes; the wind reserve dwarfs this.

$$E_{\text{mission}} = \bar{P} \cdot (t_{\text{cruise}} + t_{\text{hover}})$$

$$t_{\text{cruise}} = \frac{d_{\text{path}}}{v_{\text{ground}}}$$

$$v_{\text{ground}} = \max(0, v_{\text{cruise}} - v_{\text{headwind}})$$

The path distance `d_path` is the sum of great-circle segments along the A\*-planned route — *not* the straight-line haversine between start and goal.

### 1.3 Wind decomposition

The headwind component along bearing `β` for wind from meteorological direction `φ` (i.e. wind blowing *from* φ, *toward* φ+180°) is:

$$v_{\text{headwind}} = -|v_{\text{wind}}| \cdot \cos(\beta - (\phi + 180°))$$

A west wind (φ=270°) for an east-bound flight (β=90°) gives a *negative* headwind component (tailwind). A pure crosswind has zero projection on the flight axis (we currently do not model the small extra induced-power penalty from a crab angle — typically <5% at 30° crab).

### 1.4 Payload scaling

Adding payload `p` to a drone of MTOW `m` scales hover power as

$$\bar{P}(p) = \bar{P}_0 \cdot \left( \frac{m + p}{m} \right)^{1.5}$$

This is the standard induced-power result from momentum theory for a rotor at fixed disk loading: thrust scales linearly with weight, and induced power scales as thrust^1.5 / sqrt(2·ρ·A). For the Skydio X10, 1 kg of payload (≈40% MTOW) increases P̄ from 199 W to 330 W and reduces the still-air energy margin on the default 12.6 km mission from 60% to 33% — a meaningful operational insight, verifiable in `verify.mjs` block 7.

For delivery drones with no published battery (Wing, Zipline P2), payload scales the published range by the inverse: `range_eff = range_published × (m / (m + p))^1.5`.

We intentionally don't expose a mission-altitude slider. At sUAS altitudes (0–500 ft AGL) climb energy is on the order of `m·g·h ≈ 0.5 Wh` round-trip for a Skydio-class drone, and air-density derating is ~1% — both negligible against wind and payload effects. The regulatory altitude check uses a fixed 200 ft AGL, well within the Part 107 ceiling.

### 1.5 Drones without published battery

Wing's Hummingbird and Zipline's P2 do not publish battery capacity. For those we report **feasibility via published range** instead of an absolute Wh figure: `feasible ⇔ d_path ≤ d_max,published × 0.85`. This is flagged in the UI verdict so the operator knows the energy bar is range-based.

---

## 2. Path planner

A\* on a regular lat/lng grid. Cell cost combines distance and overflight density:

$$c_{\text{step}} = d_{\text{step}} \cdot (1 + \rho/10) + \lambda \cdot \rho$$

with `ρ ∈ [0, 10]` the population density at the destination cell and `λ = 80` metres of detour the planner will accept per unit density. The heuristic is the great-circle distance to the goal (admissible — never overestimates true cost given non-negative cell costs).

Connectivity is 8-neighbourhood. The bounding box is start/goal plus 0.05° padding, then expanded to include any no-fly polygon that actually intersects this box (so detours are possible). Grid resolution is auto-picked to keep cell size near 250 m, capped at 140×140 cells.

No-fly polygons are hard-blocked (cost ∞), with the start and goal cells force-cleared so the drone can always depart and land. If the goal sits inside a no-fly zone with no free corridor, the planner returns no path and the verdict panel reports it.

---

## 3. Risk / population exposure

Density is modelled as a sum of Gaussian peaks at population centres, with peak intensity and σ in km calibrated to a 0–10 scale where Seattle downtown ≈ 8, Bellevue ≈ 7, mid Lake Washington ≈ 6 (still within metro influence), rural ≈ 0.3.

Exposure along the path is reported as mean and peak density, with a class label inspired by **ASTM F3178 Operational Risk classes**: Desolate (<1), Sparse (<3), Populated (<6), Dense urban (≥6). Real systems substitute a rasterized density layer (WorldPop, GHS-POP, LandScan, NOAA Census tracts) for the `popDensity()` call; the downstream contract is unchanged.

---

## 4. Regulatory checks

All references current as of **June 2026**:

| Check | Source | Behaviour |
|---|---|---|
| MTOW ≤ 25 kg | 14 CFR §107.3 | Block above; would need §44807 exemption or future Part 108 type cert |
| Remote ID | 14 CFR Part 89 (effective Sep 16 2023; enforcement from late 2024) | Block if MTOW > 250 g and `has_rid: false` |
| Altitude ≤ 400 ft AGL | 14 CFR §107.51 | Warn above; structures exception applies within 400 ft horizontal |
| Cruise ≤ 100 mph | 14 CFR §107.51(b) | Warn above |
| VLOS | 14 CFR §107.31 | Block if BVLOS and operator not in `bvlos_authorized` set; else warn |
| BVLOS | Part 108 NPRM (Aug 2025) | Final rule pending as of Jun 2026; expected Q3–Q4 2026 |
| Controlled airspace | LAANC via UAS Facility Maps | Warn — LAANC required |
| Over people | 14 CFR §107.140–145 | Warn — Categories 1–4 declaration required |
| Night | 14 CFR §107.29 | Warn — anti-collision lighting required (waiver-free since Apr 2021) |

Findings are tagged `ok / warn / block`. The overall mission is `ALLOW` iff no `block`-level finding fires; `warn`s do not gate but are surfaced so the operator can document waiver / authorisation coverage.

---

## 5. Known limitations and honest caveats

- **Wind model is 1D along bearing.** Crosswind induces a small (<5%) extra power draw at typical crab angles that we don't model. Acceptable for go/no-go; not acceptable for energy planning at margin <10%.
- **Power is constant across cruise and hover.** Honest within ~10% for missions <30 min. Hover-heavy inspections at low altitude in heat will draw more.
- **Population density is a synthetic Gaussian model**, not a real raster. Use it to demonstrate the planner's risk-awareness, not for actual ConOps approval.
- **No-fly zones are simplified octagons** approximating Class B/C/D cores. Real FAA Class B has tiered shelves, TFRs change daily, and grid ceilings vary by UAS Facility Map cell. For production you'd ingest the FAA UAS Facility Maps + USNS NOTAMs.
- **Delivery drones without published battery** are scored on range only. Their absolute Wh is not displayed.
- **Battery degradation, temperature** increase mission power and shrink usable Wh; not modelled (operator should add reserve). Payload is modelled (§1.4).
- **A\* is grid-quantised.** Reported path distance carries ~5–10% overhead vs the true continuous shortest path. With risk weighting on, additional overhead is by design (the planner is trading distance for lower overflight exposure).
