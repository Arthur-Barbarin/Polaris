// Strategic (pre-departure) deconfliction over shared 4D intents.
//
// Model: each flight is a straight cruise leg between two vertiports at its
// vehicle's cruise speed, on one altitude layer, departing at some time. Two
// flights on the SAME layer conflict if their protected horizontal buffers
// (strat_horiz_m) ever overlap while both are airborne. Flights on layers
// spaced by >= strat_vert_m are vertically separated during cruise.
//
// This mirrors the FAA UTM ConOps v2.0 / ASTM F3548-21 idea of detecting
// conflicts between operational intents BEFORE takeoff and resolving them by
// adjusting the plan (here: altitude layer first, then a departure delay).
//
// SIMPLIFICATION (disclosed): we deconflict cruise legs only; the short
// climb/descent transitions between layers are handled by the tactical layer,
// not modelled as strategic vertical conflicts.

import { toENU, sub, add, scale, dot, norm } from "./geo.js";
import { ALT_LAYERS, SEP, PAD } from "../data/airspace.js";

// Build a straight-line 4D intent for a flight in the local ENU frame.
export function buildIntent(flight, ref) {
  const a = toENU(flight.origin, ref);
  const b = toENU(flight.dest, ref);
  const d = { x: b.x - a.x, y: b.y - a.y };
  const dist = Math.hypot(d.x, d.y);
  const speed = flight.vehicle.cruise_ms;
  const dur = dist / speed;
  const vel = dist > 0 ? { x: (d.x / dist) * speed, y: (d.y / dist) * speed } : { x: 0, y: 0 };
  return { a, b, dist, dur, vel, dep: flight.dep, arr: flight.dep + dur };
}

function posAt(intent, t) {
  const dt = Math.max(0, Math.min(t - intent.dep, intent.dur));
  return add(intent.a, scale(intent.vel, dt));
}

// Minimum horizontal separation between two intents over the time both are
// airborne. Returns Infinity if their airborne windows don't overlap.
export function minSep(iA, iB) {
  const t0 = Math.max(iA.dep, iB.dep);
  const t1 = Math.min(iA.arr, iB.arr);
  if (t0 >= t1) return Infinity;
  const rA = posAt(iA, t0), rB = posAt(iB, t0);
  const r = sub(rA, rB);
  const v = sub(iA.vel, iB.vel);
  const vv = dot(v, v);
  let t = vv > 1e-9 ? -dot(r, v) / vv : 0;
  t = Math.max(0, Math.min(t, t1 - t0));
  return norm(add(r, scale(v, t)));
}

// Do two flights (with candidate layer/delay applied) conflict?
function conflicts(a, b) {
  if (a.layer !== b.layer) return false; // vertically separated in cruise
  return minSep(a.intent, b.intent) < SEP.strat_horiz_m;
}

// Baseline: assign layers round-robin, no delays, count conflicting pairs.
export function countBaselineConflicts(flights, ref) {
  const items = flights.map((f, i) => ({
    layer: ALT_LAYERS[i % ALT_LAYERS.length],
    intent: buildIntent(f, ref),
  }));
  let n = 0;
  for (let i = 0; i < items.length; i++)
    for (let j = i + 1; j < items.length; j++)
      if (conflicts(items[i], items[j])) n++;
  return n;
}

// Greedy strategic deconfliction. For each flight (ordered by departure) try to
// place it on its preferred layer at its planned time; if it conflicts with an
// already-scheduled flight, try other layers, then add departure delay in
// steps until clear (up to maxDelay). Returns per-flight assignments + metrics.
export function deconflict(flights, ref, opts = {}) {
  const dStep = opts.delayStep ?? 30;      // s
  const maxDelay = opts.maxDelay ?? 900;    // s (15 min cap)
  const order = flights
    .map((f, i) => ({ f, i }))
    .sort((p, q) => p.f.dep - q.f.dep || p.i - q.i);

  const scheduled = [];
  const result = new Array(flights.length);
  const padDeps = {}; // vertiport id -> accepted departure times
  const padFree = (vpId, t) =>
    !(padDeps[vpId] || []).some((td) => Math.abs(t - td) < PAD.service_s);

  for (const { f, i } of order) {
    const prefLayer = ALT_LAYERS[i % ALT_LAYERS.length];
    const layerOrder = [prefLayer, ...ALT_LAYERS.filter((l) => l !== prefLayer)];
    let placed = null;

    outer: for (let delay = 0; delay <= maxDelay; delay += dStep) {
      const dep = f.dep + delay;
      if (!padFree(f.origin.id, dep)) continue; // origin pad busy — queue
      for (const layer of layerOrder) {
        const intent = buildIntent({ ...f, dep }, ref);
        const cand = { layer, intent };
        if (!scheduled.some((s) => conflicts(s, cand))) {
          placed = { layer, delay_s: delay, intent, resolved: true };
          break outer;
        }
      }
    }
    if (!placed) {
      // Could not fit within the delay cap — accept on preferred layer,
      // flag as residual (unresolved) conflict.
      const intent = buildIntent(f, ref);
      placed = { layer: prefLayer, delay_s: maxDelay, intent, resolved: false };
    }
    scheduled.push({ layer: placed.layer, intent: placed.intent });
    (padDeps[f.origin.id] ||= []).push(f.dep + placed.delay_s);
    result[i] = { flight: f, ...placed };
  }

  const delays = result.map((r) => r.delay_s);
  const delayTotal = delays.reduce((a, b) => a + b, 0);
  const residual = result.filter((r) => !r.resolved).length;
  const layerChanges = result.filter(
    (r, i) => r.layer !== ALT_LAYERS[i % ALT_LAYERS.length]
  ).length;
  const arrs = result.map((r) => r.intent.arr);
  const deps = result.map((r) => r.flight.dep + r.delay_s);
  const span = Math.max(1, Math.max(...arrs) - Math.min(...deps));
  const throughput = (flights.length / span) * 3600; // completed ops/hour over the busy span

  return {
    assignments: result,
    metrics: {
      n: flights.length,
      baselineConflicts: countBaselineConflicts(flights, ref),
      delayTotal_s: delayTotal,
      delayMean_s: delayTotal / flights.length,
      residual,
      layerChanges,
      throughput_ph: throughput,
    },
  };
}
