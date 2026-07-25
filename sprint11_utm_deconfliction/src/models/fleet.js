// Fleet generation + the capacity scaling sweep (the "scale it" story).

import { VERTIPORTS } from "../data/vertiports.js";
import { VEHICLE_LIST } from "../data/vehicles.js";
import { makeRng, haversine_m } from "./geo.js";
import { deconflict } from "./strategic.js";

// Generate N flights with reproducible pseudo-random OD pairs, vehicle types
// and departures over a scheduling window. Seeded => byte-for-byte repeatable.
export function generateFleet(n, seed = 42, windowSec = 600) {
  const rng = makeRng(seed);
  const pick = (arr) => arr[Math.floor(rng() * arr.length)];
  const flights = [];
  let guard = 0;
  while (flights.length < n && guard < n * 50) {
    guard++;
    const o = pick(VERTIPORTS);
    let d = pick(VERTIPORTS);
    if (d.id === o.id) continue;
    // reject implausibly long hops (> 45 km) — outside urban eVTOL range
    if (haversine_m(o, d) > 45000) continue;
    flights.push({
      id: flights.length,
      origin: { lat: o.lat, lng: o.lng, id: o.id },
      dest: { lat: d.lat, lng: d.lng, id: d.id },
      vehicle: pick(VEHICLE_LIST),
      dep: rng() * windowSec,
      priority: 0, // set below by departure order
    });
  }
  // priority = earlier departure wins (lower value = higher priority)
  flights
    .slice()
    .sort((a, b) => a.dep - b.dep)
    .forEach((f, rank) => (f.priority = rank));
  return flights;
}

// Sweep fleet size and record how strategic deconfliction copes. Returns rows
// suitable for a conflicts-vs-fleet chart, plus the identified capacity knee.
export function scalingSweep(ref, sizes, seed = 42) {
  const rows = sizes.map((n) => {
    const flights = generateFleet(n, seed);
    const { metrics } = deconflict(flights, ref);
    return {
      n,
      baselineConflicts: metrics.baselineConflicts,
      delayMean_min: metrics.delayMean_s / 60,
      residual: metrics.residual,
      throughput_ph: metrics.throughput_ph,
      layerChanges: metrics.layerChanges,
    };
  });
  // Capacity knee: first fleet size where the plan can no longer keep everyone
  // deconflicted within the delay cap (residual > 0), else null (headroom).
  const knee = rows.find((r) => r.residual > 0)?.n ?? null;
  return { rows, knee };
}
