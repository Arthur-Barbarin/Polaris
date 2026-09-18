// Live simulation stepper that drives the map animation.
//
// TIME STEP. The model is always integrated at a FIXED internal step
// (SIM_DT = 0.5 s), whatever the display rate. `step(sim, dt)` advances the
// model by `dt` simulated seconds using ceil(dt / SIM_DT) sub-steps, so the
// animation-speed control changes how fast time is shown and nothing else.
// Before this was decoupled, the speed slider was the integrator step: at 3 s
// per step a pair closing at 110 m/s jumped 330 m between samples, tunnelled
// straight through the 60 m loss-of-separation floor and was scored "resolved".
// Encounter minima are additionally taken from the analytic closest point of
// approach WITHIN each sub-step, not from the sampled endpoints, so the safety
// verdict no longer depends on the step at all.
//
// Agents fly their deconflicted cruise legs. Every step we run the tactical
// detect-and-avoid scan and, for each predicted well-clear violation, issue a
// resolution to the give-way vehicle. Crucially the resolution is NOT free: the
// vehicle takes `react_s` to commit, then opens lateral separation at a bounded
// rate `lat_rate_ms`. So a late-detected ("pop-up") intruder can leave too
// little time to recover — a genuine loss of separation. That failure envelope
// is the point of the tactical demo.

import { toLatLng, sub, norm } from "./geo.js";
import { predictPair, resolve } from "./tactical.js";
import { SEP, TACT } from "../data/airspace.js";

const unit = (v) => {
  const m = norm(v) || 1;
  return { x: v.x / m, y: v.y / m };
};
const perpRight = (u) => ({ x: u.y, y: -u.x }); // right-hand normal

export function buildSim(assignments, ref) {
  const agents = assignments.map((asg) => {
    const a = asg.intent.a, b = asg.intent.b;
    const dir = unit(sub(b, a));
    return {
      id: asg.flight.id,
      color: asg.flight.vehicle.color,
      name: asg.flight.vehicle.name,
      priority: asg.flight.priority,
      cooperative: true,
      intruder: false,
      a, b, dir, legLen: asg.intent.dist,
      speed: asg.flight.vehicle.cruise_ms,
      climb: asg.flight.vehicle.climb_ms,
      dep: asg.flight.dep + asg.delay_s,
      layer: asg.layer,
      // dynamic state
      s: 0, cross: 0, crossTarget: 0,
      alt: asg.layer, altTarget: asg.layer,
      speedFactor: 1,
      maneuver: null, // { adv, react, t } — advisory applied only after react<=0
      latRate: TACT.lat_rate_ms,
      pos: { ...a }, prevPos: { ...a }, prevAlt: asg.layer, vel: { x: 0, y: 0 },
      airborne: false, done: false,
    };
  });
  return {
    ref, agents, t: 0,
    encounters: [],            // injected-intruder test cases we track to outcome
    stats: {
      // Smallest HORIZONTAL separation seen this run, with the vertical gap at
      // that moment. A single slant range is the wrong headline here: its floor
      // is the deliberate altitude-layer spacing, so normal layered traffic
      // pinned it at ~30 m and it read as an alarm, while the quantity a
      // controller actually watches — lateral separation — reached 0 m unseen.
      minHoriz: Infinity,
      vertAtMinHoriz: Infinity,
      minSep: Infinity,        // smallest live 3-D slant separation (secondary)
      encounters: 0, resolved: 0, los: 0,
      last: null,              // { range, tcpa, outcome, minSep } of last injection
    },
  };
}

function computePos(ag) {
  const along = { x: ag.a.x + ag.dir.x * ag.s, y: ag.a.y + ag.dir.y * ag.s };
  const n = perpRight(ag.dir);
  return { x: along.x + n.x * ag.cross, y: along.y + n.y * ag.cross };
}

// 3-D-ish separation between two agents: horizontal distance + vertical gap.
function separation(A, B) {
  const h = norm(sub(A.pos, B.pos));
  const v = Math.abs(A.alt - B.alt);
  return { h, v, slant: Math.hypot(h, v) };
}

// Smallest separation actually reached between two agents DURING a sub-step,
// from the analytic closest point of approach of their relative motion over the
// step rather than from the two sampled endpoints.
function minSepOverStep(A, B, dt) {
  const end = separation(A, B);
  if (!(dt > 0)) return end;
  const r0 = sub(A.prevPos, B.prevPos);
  const dA = sub(A.pos, A.prevPos), dB = sub(B.pos, B.prevPos);
  const v = { x: (dA.x - dB.x) / dt, y: (dA.y - dB.y) / dt };
  const vv = v.x * v.x + v.y * v.y;
  let t = vv > 1e-12 ? -(r0.x * v.x + r0.y * v.y) / vv : 0;
  t = Math.max(0, Math.min(t, dt));
  const h = norm({ x: r0.x + v.x * t, y: r0.y + v.y * t });
  // altitude is integrated linearly over the step, so interpolate it the same way
  const vA = A.alt - (A.prevAlt ?? A.alt), vB = B.alt - (B.prevAlt ?? B.alt);
  const altA = (A.prevAlt ?? A.alt) + vA * (t / dt);
  const altB = (B.prevAlt ?? B.alt) + vB * (t / dt);
  const vert = Math.abs(altA - altB);
  const cand = { h, v: vert, slant: Math.hypot(h, vert) };
  return cand.h < end.h ? cand : end;
}

// Fixed internal integration step. Everything physical is integrated at this
// step; the display rate only decides how many sub-steps run per frame.
export const SIM_DT = 0.5;

// Advance the model by `dt` SIMULATED seconds, at the fixed internal step.
export function step(sim, dt, sep = SEP) {
  const n = Math.max(1, Math.ceil(dt / SIM_DT - 1e-9));
  const h = dt / n;
  let conflicts = [];
  for (let k = 0; k < n; k++) conflicts = stepOnce(sim, h, sep);
  return conflicts;
}

function stepOnce(sim, dt, sep = SEP) {
  sim.t += dt;

  // 1) advance each agent (maneuvers are latency + rate limited)
  for (const ag of sim.agents) {
    if (ag.done) { ag.airborne = false; continue; }
    if (sim.t < ag.dep) { ag.airborne = false; ag.pos = computePos(ag); continue; }
    ag.airborne = true;
    ag.prevPos = ag.pos;
    ag.prevAlt = ag.alt;

    if (ag.maneuver) {
      ag.maneuver.t -= dt;
      if (ag.maneuver.react > 0) {
        ag.maneuver.react -= dt;                 // still reacting — fly straight
      } else if (!ag.maneuver.applied) {
        const adv = ag.maneuver.adv;             // commit the advisory now
        if (adv.type === "speed") ag.speedFactor = 0.65;
        else if (adv.type === "vertical") ag.altTarget = ag.alt + adv.dAlt;
        else {
          // Turn right and open the required offset at the rate the SELECTED
          // turn angle actually produces (speed * sin(angle)), capped by the
          // airframe limit. The angle chosen by `resolve` therefore matters.
          ag.crossTarget = sep.daa_hmd_m * 1.15;
          ag.latRate = adv.latRate ?? TACT.lat_rate_ms;
        }
        ag.maneuver.applied = true;
      }
      if (ag.maneuver.t <= 0) {
        ag.maneuver = null;
        ag.crossTarget = 0; ag.altTarget = ag.layer; ag.speedFactor = 1;
        ag.latRate = TACT.lat_rate_ms;
      }
    }

    ag.s += ag.speed * ag.speedFactor * dt;
    const dCross = ag.crossTarget - ag.cross;      // bounded lateral rate
    const latRate = ag.latRate ?? TACT.lat_rate_ms;
    ag.cross += Math.sign(dCross) * Math.min(Math.abs(dCross), latRate * dt);
    const dAlt = ag.altTarget - ag.alt;            // bounded vertical rate
    ag.alt += Math.sign(dAlt) * Math.min(Math.abs(dAlt), ag.climb * dt);

    ag.pos = computePos(ag);
    ag.vel = { x: (ag.pos.x - ag.prevPos.x) / dt, y: (ag.pos.y - ag.prevPos.y) / dt };
    if (norm(ag.vel) < 1e-6) ag.vel = { x: ag.dir.x * ag.speed, y: ag.dir.y * ag.speed };

    if (ag.s >= ag.legLen) { ag.done = true; ag.airborne = false; }
  }

  // 2) tactical scan over airborne pairs → issue advisories to give-way vehicles
  const conflicts = [];
  for (let i = 0; i < sim.agents.length; i++) {
    for (let j = i + 1; j < sim.agents.length; j++) {
      const A = sim.agents[i], B = sim.agents[j];
      if (!A.airborne || !B.airborne) continue;
      const p = predictPair(A, B, sep);
      const s = minSepOverStep(A, B, dt);
      if (s.slant < sim.stats.minSep) sim.stats.minSep = s.slant;
      if (s.h < sim.stats.minHoriz) {
        sim.stats.minHoriz = s.h;
        sim.stats.vertAtMinHoriz = s.v;
      }
      if (p.wellClearViolation) conflicts.push({ i, j, p });
    }
  }
  for (const { i, j } of conflicts) {
    const A = sim.agents[i], B = sim.agents[j];
    let give, keep;
    if (!A.cooperative && B.cooperative) { give = B; keep = A; }
    else if (!B.cooperative && A.cooperative) { give = A; keep = B; }
    else { give = A.priority > B.priority ? A : B; keep = give === A ? B : A; }
    if (give.maneuver || !give.cooperative) continue;
    const adv = resolve(give, keep, sep);
    give.maneuver = { adv, react: TACT.react_s, applied: false, t: 16 };
    give.conflictColor = true;
  }
  for (const ag of sim.agents) if (!ag.maneuver) ag.conflictColor = false;

  // 3) score the tracked intruder encounters (resolved vs loss of separation).
  // The minimum is the analytic CPA WITHIN this sub-step, not the endpoint
  // sample — otherwise a fast pair tunnels through the LoS floor unseen.
  for (const e of sim.encounters) {
    if (e.classified) continue;
    const A = e.intruder, B = e.target;
    if (!A.airborne || !B.airborne || A.done || B.done) { classify(sim, e); continue; }
    const s = minSepOverStep(A, B, dt);
    if (s.h < e.minH) { e.minH = s.h; e.vAtMinH = s.v; e.minSlant = s.slant; }
    // past closest approach once they start diverging
    const p = predictPair(A, B, sep);
    if (!p.closing && e.minH < Infinity) classify(sim, e);
  }

  return conflicts;
}

function classify(sim, e) {
  e.classified = true;
  const los = e.minH < SEP.los_horiz_m && e.vAtMinH < SEP.los_vert_m;
  sim.stats.encounters++;
  if (los) sim.stats.los++; else sim.stats.resolved++;
  sim.stats.last = {
    range: Math.round(e.range),
    tcpa: e.tcpa,
    closure: Math.round(e.closure ?? 0),
    target: e.targetName ?? "",
    outcome: los ? "LOSS OF SEP" : "resolved",
    minSep: Math.round(e.minSlant),
  };
}

// Live view model for the map (lat/lng + status).
export function viewModel(sim) {
  return sim.agents
    .filter((a) => a.airborne)
    .map((a) => ({
      id: a.id, color: a.intruder ? "#ef4444" : a.color, name: a.name,
      intruder: a.intruder, maneuvering: !!(a.maneuver && a.maneuver.applied), alt: a.alt,
      ...toLatLng(a.pos, sim.ref),
      heading: (Math.atan2(a.vel.x, a.vel.y) * 180) / Math.PI,
    }));
}

// Spawn a non-cooperative intruder on a converging course with an airborne
// cooperative agent. `rangeM` is the pop-up detection range: small = late
// detection = little time to recover.
//
// The target is drawn from a caller-supplied PRNG (`opts.rng`), not
// Math.random, so an injection is reproducible from the scenario seed. Closure
// speed depends on which vehicle is drawn (VoloCity 25 m/s to Joby S4 89 m/s
// against a 55 m/s intruder, i.e. 80 to 144 m/s), so the range alone does not
// determine the difficulty: the realised closure and time-to-CPA are returned
// and must be displayed alongside the verdict.
export function injectConflict(sim, opts = {}, sep = SEP) {
  const rangeM = opts.rangeM ?? 1200;
  const intrSpeed = opts.speed ?? 55;
  const rng = opts.rng ?? Math.random;
  const targets = sim.agents.filter((a) => a.airborne && a.cooperative && !a.done);
  if (!targets.length) return null;
  const T = targets[Math.floor(rng() * targets.length)];
  const dir = unit(T.vel.x || T.vel.y ? T.vel : T.dir);
  const start = { x: T.pos.x + dir.x * rangeM, y: T.pos.y + dir.y * rangeM };
  const heading = { x: -dir.x, y: -dir.y }; // head-on toward T
  const closure = intrSpeed + (T.speed || 50);
  const tcpa = rangeM / closure;
  const id = 10000 + sim.agents.length;
  const intruder = {
    id, color: "#ef4444", name: "Non-cooperative intruder",
    priority: -1, cooperative: false, intruder: true,
    a: start, b: { x: start.x + heading.x * 8000, y: start.y + heading.y * 8000 },
    dir: heading, legLen: 8000, speed: intrSpeed, climb: 3,
    dep: sim.t, layer: T.alt,
    s: 0, cross: 0, crossTarget: 0, alt: T.alt, altTarget: T.alt, speedFactor: 1,
    maneuver: null, latRate: TACT.lat_rate_ms,
    pos: { ...start }, prevPos: { ...start }, prevAlt: T.alt,
    vel: { x: heading.x * intrSpeed, y: heading.y * intrSpeed },
    airborne: true, done: false,
  };
  sim.agents.push(intruder);
  sim.encounters.push({
    intruder, target: T, range: rangeM, tcpa, closure,
    targetName: T.name, targetSpeed: T.speed,
    minH: Infinity, vAtMinH: Infinity, minSlant: Infinity, classified: false,
  });
  return { tcpa, rangeM, closure, targetName: T.name };
}
