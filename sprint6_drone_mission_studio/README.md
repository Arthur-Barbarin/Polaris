# Sprint 6 — Drone Mission Studio

Energy-aware, risk-aware, regulation-aware mission planner for commercial sUAS.

**Stack:** React · Leaflet · Recharts · Vite (pure frontend, no backend)

---

## What it does

Most drone planning tools answer: *"Can I fly here?"*
This tool answers: *"Will the mission close — and what binds first: energy, risk, or regulation?"*

Pick a real drone (Skydio X10, DJI M30, Wing Hummingbird, Zipline P2), drop a start and goal on the map, set wind and operational conditions. The tool returns:

1. An **A\*-planned route** that respects no-fly zones and biases away from dense overflight
2. A **mission energy budget** in Wh, with available reserve and headwind-component decomposition
3. A **population exposure class** along the planned path (ASTM F3178-inspired)
4. A **regulatory verdict** against FAA Part 107 / Remote ID / Part 108 BVLOS NPRM status as of June 2026
5. A **wind sensitivity curve** showing how energy scales with headwind, and where the mission breaks

**Distinct from Sprint 2 (Drone Deployment Decision Engine):**
Sprint 2 returns a binding constraint *label* for a given operational scenario.
Sprint 6 returns an actual *planned route* on a real map, with cost and risk integrated over the path. The question shifts from "can this be done in principle" to "does this specific corridor close, and where does the margin disappear."

---

## Model

### Energy (`src/models/energy.js`)

Power is derived empirically from manufacturer-quoted endurance, not from a rotor-geometry model that an operator would reasonably distrust:

```
P̄ [W]      = battery_Wh × 0.85 / (t_max_h)        # 15% usable-battery reserve
E_mission   = P̄ × (cruise_time + hover_time)
t_cruise    = distance / ground_speed
ground_speed = max(0, cruise_airspeed − headwind_component)
```

Headwind component along the great-circle bearing: standard meteorological convention (wind *from* φ blows *toward* φ+180°), projected onto the flight vector.

For delivery drones with no published battery capacity (Wing, Zipline P2), feasibility falls back to a range check: `distance ≤ published_range × 0.85`. This is documented in the UI as "feasibility via range only."

Verification (`node verify.mjs`) confirms derived P̄ falls in the 80–87 W/kg band for the multirotors, consistent with the published Mavic 3 benchmark of ≈95 W/kg.

### Risk (`src/models/risk.js`)

Population density is modelled as a sum of Gaussian "city centers" with peak intensities and characteristic radii. Classification (Desolate / Sparse / Populated / Dense urban) follows ASTM F3178 Operational Risk language. The intent is a defensible interactive demo; to drop in WorldPop, GHS-POP, or LandScan tiles, replace `popDensity()` — the downstream API (mean, peak, class label) is unchanged.

### Planner (`src/models/planner.js`)

A\* on a regular lat/lng grid auto-sized to keep cell size near 250 m. 8-connected, with great-circle heuristic (admissible). Cell cost is `step_distance × (1 + density/10) + 80·density` — the planner will accept up to ~80 m of detour per unit of additional density. No-fly polygons are hard-blocked.

The bbox is expanded to include any no-fly polygon that actually overlaps the corridor, so the planner has room to detour. Polygons far from the corridor are ignored (they'd just coarsen the grid).

### Regulatory (`src/models/regulatory.js`)

Checks against 14 CFR Part 107, Part 89 (Remote ID), and the Part 108 NPRM status (published Aug 2025; final rule pending as of June 2026, expected Q3–Q4 2026). Findings are tagged **ok / warn / block** so the operator can see what's a hard stop versus what needs documentation. References cited inline.

---

## Drone catalogue

| Drone | MTOW | Battery | Endurance | Cruise | Sources |
|---|---|---|---|---|---|
| Skydio X10 | 2.49 kg | 156.17 Wh | 40 min | 13 m/s | [SKYDIO-X10] |
| DJI Matrice 30 | 3.77 kg | 263.2 Wh (2×TB30) | 41 min | 15 m/s | [DJI-M30] |
| Zipline P2 Zip | ~20 kg | n/p | 18 min | 31 m/s | [ZIPLINE] |
| Wing Hummingbird | 6.8 kg | n/p | 11 min | 29 m/s | [WING] |

Sources accessed June 2026:
- [SKYDIO-X10]  skydio.com/x10/technical-specs · skydio.com/x10/faqs
- [DJI-M30]     enterprise.dji.com/matrice-30/specs
- [ZIPLINE]     zipline.com/about/zipline-fact-sheet
- [WING]        FAA Christiansburg EA · wing.com

---

## Verification

`verify.mjs` reproduces every number the UI displays, with expected ranges noted in-line. Output blocks: power & range from published endurance, wind decomposition unit tests, default-mission distance and energy, headwind sensitivity sweep, regulatory matrix across operational scenarios, no-fly detour behaviour, population density spot checks.

---

## Polaris context

Sprint 6 of the [Polaris Decision Modeling Studio](../README.md).
Synthesises Sprint 2 (regulatory go/no-go) + Sprint 3 (battery physics) + Sprint 5 (operational economics) into a single live planning surface.

*Engineering clarity for complex futures.*
