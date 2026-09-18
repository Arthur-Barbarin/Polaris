// Fleet generation + the capacity scaling sweep (the "scale it" story).

import { VERTIPORTS } from "../data/vertiports.js";
import { VEHICLE_LIST } from "../data/vehicles.js";
import { makeRng, haversine_m } from "./geo.js";
import { deconflict } from "./strategic.js";

// Generate N flights with reproducible pseudo-random OD pairs, vehicle types
// and departures over a scheduling window. Seeded => byte-for-byte repeatable.
export function generateFleet(n, seed = 42, windowSec = 600, vertiports = VERTIPORTS) {
  const rng = makeRng(seed);
  const pick = (arr) => arr[Math.floor(rng() * arr.length)];
  const flights = [];
  let guard = 0;
  while (flights.length < n && guard < n * 50) {
    guard++;
    const o = pick(vertiports);
    let d = pick(vertiports);
    if (d.id === o.id) continue;
    // The vehicle is drawn BEFORE the hop is accepted, so the hop can be
    // checked against THAT vehicle's published range. A single global 45 km
    // filter applied before the draw assigned a VoloCity (35 km published)
    // hops of up to 41 km — 18% of its Paris flights — while refusing a Joby S4
    // (240 km) anything past 45 km. No reserve is applied: this sprint carries
    // no energy state, so range here is a feasibility ceiling, not an
    // operational range.
    const vehicle = pick(VEHICLE_LIST);
    if (haversine_m(o, d) > vehicle.range_km * 1000) continue;
    flights.push({
      id: flights.length,
      origin: { lat: o.lat, lng: o.lng, id: o.id },
      dest: { lat: d.lat, lng: d.lng, id: d.id },
      vehicle,
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
//
// CAPACITY IS DEFINED AT A SERVICE LEVEL, NOT BY A LIST POSITION. The knee is
// the demand at which the planner can no longer accept `serviceLevel` of the
// requested operations (default 95%), obtained by linear interpolation between
// sweep points. The previous definition — "first entry in the sweep list with
// at least one rejection" — moved with the granularity of the list (omitting
// 100 from the list moved the published knee from 100 to 120) and rested on a
// single rejected flight.
export function scalingSweep(ref, sizes, seed = 42, vertiports = VERTIPORTS) {
  const rows = sizes.map((n) => {
    const flights = generateFleet(n, seed, 600, vertiports);
    const { metrics } = deconflict(flights, ref);
    return {
      n,
      baselineConflicts: metrics.baselineConflicts,
      delayMean_min: metrics.delayMean_s / 60,
      residual: metrics.residual,
      accepted: metrics.accepted,
      acceptanceRate: metrics.acceptanceRate,
      throughput_ph: metrics.throughput_ph,
      layerChanges: metrics.layerChanges,
    };
  });
  return { rows, knee: kneeAtServiceLevel(rows) };
}

// Interpolated demand at which the acceptance rate first falls below the
// service level. Returns null when the sweep never reaches it (headroom).
export function kneeAtServiceLevel(rows, serviceLevel = 0.95) {
  for (let i = 0; i < rows.length; i++) {
    const a = rows[i].acceptanceRate;
    if (a >= serviceLevel) continue;
    if (i === 0) return rows[0].n;
    const prev = rows[i - 1];
    const f = (prev.acceptanceRate - serviceLevel) / (prev.acceptanceRate - a);
    return Math.round(prev.n + f * (rows[i].n - prev.n));
  }
  return null;
}

const quantile = (sorted, q) => {
  if (!sorted.length) return null;
  const i = (sorted.length - 1) * q, lo = Math.floor(i), hi = Math.ceil(i);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (i - lo);
};

// Capacity is a property of the network AND of the demand profile. One random
// draw is not a capacity study: across seeds the knee of this network spans
// roughly a factor of two. Run `nSeeds` independent demand draws and report the
// median with a 10th–90th percentile band, per fleet size and for the knee.
export function capacityBand(ref, sizes, opts = {}) {
  const nSeeds = opts.nSeeds ?? 30;
  const seed0 = opts.seed0 ?? 1;
  const serviceLevel = opts.serviceLevel ?? 0.95;
  const vertiports = opts.vertiports ?? VERTIPORTS;

  const perSeed = [];
  for (let k = 0; k < nSeeds; k++) {
    const seed = seed0 + k;
    const rows = sizes.map((n) => {
      const { metrics } = deconflict(generateFleet(n, seed, 600, vertiports), ref);
      return {
        n,
        accepted: metrics.accepted,
        acceptanceRate: metrics.acceptanceRate,
        rejected: metrics.rejected,
        delayMean_min: metrics.delayMean_s / 60,
        throughput_ph: metrics.throughput_ph,
        baselineConflicts: metrics.baselineConflicts,
      };
    });
    perSeed.push({ seed, rows, knee: kneeAtServiceLevel(rows, serviceLevel) });
  }

  const band = sizes.map((n, i) => {
    const pick = (f) => perSeed.map((s) => f(s.rows[i])).sort((a, b) => a - b);
    const acc = pick((r) => r.accepted);
    const del = pick((r) => r.delayMean_min);
    const con = pick((r) => r.baselineConflicts);
    return {
      n,
      accepted_p10: quantile(acc, 0.1), accepted_med: quantile(acc, 0.5), accepted_p90: quantile(acc, 0.9),
      delay_p10: quantile(del, 0.1), delay_med: quantile(del, 0.5), delay_p90: quantile(del, 0.9),
      conflicts_med: quantile(con, 0.5),
    };
  });

  const knees = perSeed.map((s) => s.knee).filter((k) => k != null).sort((a, b) => a - b);
  return {
    band,
    nSeeds,
    serviceLevel,
    knee_med: quantile(knees, 0.5),
    knee_p10: quantile(knees, 0.1),
    knee_p90: quantile(knees, 0.9),
    kneeSeedsReached: knees.length,
  };
}
