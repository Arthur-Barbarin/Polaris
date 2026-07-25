// Live simulation stepper that drives the map animation.
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
      pos: { ...a }, prevPos: { ...a }, vel: { x: 0, y: 0 },
      airborne: false, done: false,
    };
  });
  return {
    ref, agents, t: 0,
    encounters: [],            // injected-intruder test cases we track to outcome
    stats: {
      minSep: Infinity,        // smallest live 3-D separation seen this run
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

export function step(sim, dt, sep = SEP) {
  sim.t += dt;

  // 1) advance each agent (maneuvers are latency + rate limited)
  for (const ag of sim.agents) {
    if (ag.done) { ag.airborne = false; continue; }
    if (sim.t < ag.dep) { ag.airborne = false; ag.pos = computePos(ag); continue; }
    ag.airborne = true;
    ag.prevPos = ag.pos;

    if (ag.maneuver) {
      ag.maneuver.t -= dt;
      if (ag.maneuver.react > 0) {
        ag.maneuver.react -= dt;                 // still reacting — fly straight
      } else if (!ag.maneuver.applied) {
        const adv = ag.maneuver.adv;             // commit the advisory now
        if (adv.type === "speed") ag.speedFactor = 0.6;
        else if (adv.type === "vertical") ag.altTarget = ag.alt + adv.dAlt;
        else ag.crossTarget = sep.daa_hmd_m * 1.15; // turn right, open ~170 m
        ag.maneuver.applied = true;
      }
      if (ag.maneuver.t <= 0) {
        ag.maneuver = null;
        ag.crossTarget = 0; ag.altTarget = ag.layer; ag.speedFactor = 1;
      }
    }

    ag.s += ag.speed * ag.speedFactor * dt;
    const dCross = ag.crossTarget - ag.cross;      // bounded lateral rate
    ag.cross += Math.sign(dCross) * Math.min(Math.abs(dCross), TACT.lat_rate_ms * dt);
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
      const s = separation(A, B);
      if (s.slant < sim.stats.minSep) sim.stats.minSep = s.slant;
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

  // 3) score the tracked intruder encounters (resolved vs loss of separation)
  for (const e of sim.encounters) {
    if (e.classified) continue;
    const A = e.intruder, B = e.target;
    if (!A.airborne || !B.airborne || A.done || B.done) { classify(sim, e); continue; }
    const s = separation(A, B);
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

// Spawn a non-cooperative intruder on a converging course with a random
// airborne cooperative agent. `rangeM` is the pop-up detection range: small =
// late detection = little time to recover. Returns the predicted time-to-CPA.
export function injectConflict(sim, opts = {}, sep = SEP) {
  const rangeM = opts.rangeM ?? 1200;
  const intrSpeed = opts.speed ?? 55;
  const targets = sim.agents.filter((a) => a.airborne && a.cooperative && !a.done);
  if (!targets.length) return null;
  const T = targets[Math.floor(Math.random() * targets.length)];
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
    maneuver: null, pos: { ...start }, prevPos: { ...start },
    vel: { x: heading.x * intrSpeed, y: heading.y * intrSpeed },
    airborne: true, done: false,
  };
  sim.agents.push(intruder);
  sim.encounters.push({
    intruder, target: T, range: rangeM, tcpa,
    minH: Infinity, vAtMinH: Infinity, minSlant: Infinity, classified: false,
  });
  return { tcpa, rangeM };
}
