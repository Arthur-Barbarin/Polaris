# Sprint 15 — Satellite Constellation Coverage Studio

**Stack:** React · Leaflet · Recharts · Vite

An interactive design-space explorer for satellite constellations. Set a shell's
altitude, inclination, plane count and elevation mask — and watch the satellites
propagate, their footprints merge into a coverage blanket, and the numbers that
actually decide a constellation's business case update live: **global coverage %,
revisit gap at a chosen ground site, and how many satellites you need for
continuous coverage.**

> Answers: *"How many satellites do I need — and what does moving the shell up or
> down do to that number?"*

---

## The three things a visitor should try

1. **Load Iridium NEXT, watch it close.** 66 satellites, 6 near-polar planes.
   Footprints merge until the globe is continuously covered — the model
   reproduces Iridium's actual design claim (≥99% instantaneous global coverage,
   zero gap over Paris and Svalbard) from published design parameters alone.
2. **Switch to Starlink's 53° shell and look at the poles.** The
   coverage-by-latitude chart drops to zero above ~60°. Select McMurdo (78°S) as
   the ground site and it never sees a satellite. That's not a bug — a 53°
   inclination physically cannot serve the poles, which is exactly why Iridium
   and OneWeb fly near-polar.
3. **Drag the altitude slider.** Watch the "satellites for global coverage"
   number collapse as the shell rises — 48 satellites give 62% coverage at
   600 km, 99% at 1200 km, 100% at 2000 km. That single curve *is* the
   constellation-design argument: satellites vs altitude vs launch cost vs link
   budget.

---

## What's modelled (and what isn't)

**Orbits.** Circular orbits, two-body motion plus the secular **J2 nodal
precession** — the dominant perturbation, and the one that makes sun-synchronous
orbits possible. Sub-satellite points are computed in ECI and rotated into an
Earth-fixed frame.

**Coverage.** A satellite covers a spherical cap of half-angle
`λ = acos((Re/(Re+h))·cos ε) − ε` for minimum elevation angle `ε`. Global
coverage is an **area-weighted** grid statistic (cells weighted by `cos(lat)`,
because a 2°×2° cell at 80°N has ~17% the area of one at the equator — getting
this wrong is the classic way to overstate polar coverage). Site revisit
propagates 24 h and extracts coverage fraction, longest gap, mean gap and passes.

**Constellations.** Walker **Delta** (nodes over 360°, as GPS/Galileo/Starlink)
and Walker **Star** (nodes over 180°, as Iridium/OneWeb) in `T/P/F` notation.

**Honesty notes — the important part:**

- **This is a design-space explorer, not an ephemeris service.** No TLE ingest,
  no drag, no solar radiation pressure, no third-body, no manoeuvres or
  station-keeping. Longitudes are epoch-relative (GMST = 0 at t = 0), so absolute
  positions are not claimed — coverage statistics are rotation-invariant and are.
- **Presets are published *design* parameters, primary shell only.** Real systems
  have multiple shells, spares, drifting phases and replenishment.
- **Coverage ≠ service.** Link budget, spectrum, capacity, inter-satellite links
  and ground-segment throughput are all out of scope.
- Constants are WGS-84 / EGM-96 (`μ`, `Re`, `J2`) and IERS (Earth rotation rate).

---

## Reproduce every number

```bash
npm install
node verify.mjs      # 34 checks against independently published values
npm run dev          # studio at http://localhost:5173
```

`verify.mjs` deliberately checks the model against **outside references**, not
against itself:

| check | model | published |
|---|---|---|
| Geostationary altitude (from one sidereal day) | 35 786.0 km | 35 786 km |
| Sun-synchronous inclination @ 500 / 800 km | 97.40° / 98.60° | ≈97.4° / ≈98.6° |
| SSO nodal drift | 0.9856 °/day | 0.9856 °/day (360°/yr) |
| GPS orbital period | 11.965 h | 11h58m |
| ISS / Starlink / Iridium periods | 92.97 / 95.65 / 100.45 min | ≈92.8 / 95.6 / 100.4 |
| Starlink footprint radius @ 25° elev | 941 km | ≈940 km cell |
| Grid coverage vs spherical-cap formula | Δ 0.03% | analytic |

It also reproduces two *system-level* claims: Iridium's continuous global
coverage, and the fact that Starlink's 53° shell gives 0% coverage above 80°
latitude.

**One honest finding.** In the idealised Walker Star model the **equator is the
thin seam** — orbit planes converge at the poles and spread widest at the
equator, so Singapore sees a peak of 2 satellites against Svalbard's 10, and a
~90 s gap appears that the real 66-satellite system closes with spares and
station-keeping. The audit asserts the physics rather than the marketing claim.

See `MODEL.md` for derivations, constants and sources.

---

*Engineering clarity for complex futures.*
