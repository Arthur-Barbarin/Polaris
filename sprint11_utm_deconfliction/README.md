# Sprint 11 — UTM Fleet Deconfliction Studio

**Stack:** React · Leaflet · Recharts · Vite

A live digital twin of an urban-air-mobility (UAM) traffic network over the
Paris eVTOL vertiport sites. It runs **strategic deconfliction** (pre-departure,
over shared 4D operational intents) and **tactical detect-and-avoid** (in-flight
well-clear resolution) on a fleet you can scale from 5 to 150 simultaneous
operations — and shows you the fleet size at which the airspace saturates.

> Answers: *"How many eVTOL operations can this network absorb before
> deconfliction can no longer keep them separated — and when two aircraft do
> converge in flight, does the give-way vehicle resolve it in time?"*

---

## The two things a visitor should try

1. **Drag the fleet-size slider up.** Watch aircraft fill the Paris corridors,
   the strategic planner spread them across altitude layers and departure slots,
   and the **capacity-scaling chart** trace conflicts and mean delay against
   fleet size until it hits the **capacity knee** — the number to put in front
   of a vertiport operator.
2. **Click "Inject conflict."** A non-cooperative intruder is spawned on a
   head-on course with a live aircraft. The tactical layer predicts the loss of
   well clear, the cooperative vehicle executes a resolution maneuver (speed
   brake, altitude step, or a right-hand offset), and the "conflicts resolved"
   counter ticks up — in front of you, not in a screenshot.

---

## What's modelled (and what isn't)

**Strategic layer** — every flight is a straight cruise leg between two
vertiports at its vehicle's published cruise speed, on one of six altitude
layers, departing at some time. Two flights on the same layer conflict if their
horizontal protection buffers ever overlap while both are airborne. A greedy
planner resolves conflicts by (1) moving a flight to a free altitude layer, then
(2) delaying its departure — subject to a **vertiport pad-throughput limit**
(one launch per pad every 90 s). Pad throughput, not free-airspace conflict, is
what saturates the network — matching the constraint most cited in NASA UAM /
EASA / Uber Elevate capacity studies.

**Tactical layer** — each simulation step tests every airborne pair for a
predicted loss of **DAA well clear** using the RTCA DO-365 formulation (horizontal
miss distance + vertical separation + modified time-to-CPA). On a violation, the
give-way vehicle searches a small ordered maneuver set and takes the first that
restores well clear.

**Honesty notes (the important part):**

- **All traffic is synthetic.** No real flight plans, no live surveillance, no
  claim of a real service linking these sites.
- **The separation thresholds are illustrative, not regulatory.** There is no
  ratified separation minimum for low-altitude UAM. The strategic buffer
  (300 m), DAA well-clear (150 m / 30 m / 25 s) and pad service time (90 s) are
  values in the range discussed in the public UAM literature, and **every one is
  editable in `src/data/airspace.js`**. DO-365's actual DWC for large UAS
  (4000 ft / 450 ft / 35 s) is far larger and is documented in `MODEL.md`.
- **The tactical logic is a simplified geometric well-clear test**, not the
  ACAS-Xu / DO-386 optimised lookup-table logic — which is not claimed.
- **Cruise legs are deconflicted; the short climb/descent transitions are
  handled tactically**, not as strategic vertical conflicts.

The Paris vertiport sites (Austerlitz Seine barge, Pontoise-Cormeilles,
Saint-Cyr, Issy heliport, Le Bourget, Versailles-Satory, La Défense, CDG, Orly)
are the real locations used or studied in the Groupe ADP / RATP
*Re.Invent Air Mobility* programme around 2024; their use as one connected
on-demand network is illustrative.

---

## Reproduce every number

```bash
npm install
node verify.mjs      # audits CPA math, tau, well-clear, deconfliction, scaling
npm run dev          # live studio at http://localhost:5173
```

`verify.mjs` is deterministic (seeded PRNG). It reconstructs the CPA geometry
against closed-form answers, the DO-365 modified-tau, the well-clear prediction
and resolution, the strategic plan's conflict reduction, and the full capacity
sweep — so every figure the UI displays can be independently checked. Headline
result at seed 42: baseline airspace conflicts grow from 0 (10 ops) to 40
(150 ops); mean departure delay climbs from 0.3 to 7.5 min; the first
unresolved operation appears near **100–120 ops** — the capacity knee.

See `MODEL.md` for the full derivation, constants, and sources.

---

*Engineering clarity for complex futures.*
