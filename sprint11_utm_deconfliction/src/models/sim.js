// Live simulation stepper that drives the map animation.
//
// Agents fly their deconflicted cruise legs. Every step we run the tactical
// detect-and-avoid scan and, for each predicted well-clear violation, apply the
// resolution advisory to the give-way vehicle. Velocity is taken from the
// finite-difference of position, so every maneuver (speed brake, vertical step,
// lateral offset) is automatically reflected in the next conflict prediction.

import { toENU, toLatLng, sub, norm } from "./geo.js";
import { predictPair, resolve } from "./tactical.js";
import { SEP } from "../data/airspace.js";

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
      maneuver: null, // { type, t } cooldown timer
      pos: { ...a }, prevPos: { ...a }, vel: { x: 0, y: 0 },
      airborne: false, done: false,
    };
  });
  return {
    ref, agents, t: 0,
    stats: { losEvents: 0, conflictsResolved: 0, minSep: Infinity, maneuvers: 0 },
    _activePairs: new Set(),
  };
}

function computePos(ag) {
  const along = {
    x: ag.a.x + ag.dir.x * ag.s,
    y: ag.a.y + ag.dir.y * ag.s,
  };
  const n = perpRight(ag.dir);
  return { x: along.x + n.x * ag.cross, y: along.y + n.y * ag.cross };
}

export function step(sim, dt, sep = SEP) {
  sim.t += dt;
  // 1) advance each agent
  for (const ag of sim.agents) {
    if (ag.done) { ag.airborne = false; continue; }
    if (sim.t < ag.dep) { ag.airborne = false; ag.pos = computePos(ag); continue; }
    ag.airborne = true;
    ag.prevPos = ag.pos;

    // maneuver cooldown
    if (ag.maneuver) {
      ag.maneuver.t -= dt;
      if (ag.maneuver.t <= 0) { ag.maneuver = null; ag.crossTarget = 0; ag.altTarget = ag.layer; ag.speedFactor = 1; }
    } else {
      ag.crossTarget = 0; ag.altTarget = ag.layer; ag.speedFactor = 1;
    }

    // progress along leg
    ag.s += ag.speed * ag.speedFactor * dt;
    // lateral offset slews toward target at 25 m/s (or decays home)
    const dCross = ag.crossTarget - ag.cross;
    ag.cross += Math.sign(dCross) * Math.min(Math.abs(dCross), 25 * dt);
    // altitude slews toward target at climb rate
    const dAlt = ag.altTarget - ag.alt;
    ag.alt += Math.sign(dAlt) * Math.min(Math.abs(dAlt), ag.climb * dt);

    ag.pos = computePos(ag);
    ag.vel = { x: (ag.pos.x - ag.prevPos.x) / dt, y: (ag.pos.y - ag.prevPos.y) / dt };
    if (norm(ag.vel) < 1e-6) ag.vel = { x: ag.dir.x * ag.speed, y: ag.dir.y * ag.speed };

    if (ag.s >= ag.legLen) { ag.done = true; ag.airborne = false; }
  }

  // 2) tactical scan over airborne pairs
  const conflicts = [];
  const nowPairs = new Set();
  for (let i = 0; i < sim.agents.length; i++) {
    for (let j = i + 1; j < sim.agents.length; j++) {
      const A = sim.agents[i], B = sim.agents[j];
      if (!A.airborne || !B.airborne) continue;
      const p = predictPair(A, B, sep);
      if (p.curHoriz < sim.stats.minSep) sim.stats.minSep = p.curHoriz;
      if (p.los) {
        const key = `los:${i}:${j}`;
        if (!sim._activePairs.has(key)) sim.stats.losEvents++;
        nowPairs.add(key);
      }
      if (p.wellClearViolation) {
        conflicts.push({ i, j, p });
        const key = `cfl:${i}:${j}`;
        nowPairs.add(key);
        if (!sim._activePairs.has(key)) sim.stats.conflictsResolved++;
      }
    }
  }
  sim._activePairs = nowPairs;

  // 3) issue resolution advisories to give-way vehicles
  for (const { i, j, p } of conflicts) {
    const A = sim.agents[i], B = sim.agents[j];
    // non-cooperative (intruder) never maneuvers; else lower priority gives way
    let give, keep;
    if (!A.cooperative && B.cooperative) { give = B; keep = A; }
    else if (!B.cooperative && A.cooperative) { give = A; keep = B; }
    else { give = A.priority > B.priority ? A : B; keep = give === A ? B : A; }
    if (give.maneuver) continue; // already maneuvering
    const adv = resolve(give, keep, sep);
    give.maneuver = { type: adv.type, t: 12 }; // 12 s advisory hold
    give.conflictColor = true;
    sim.stats.maneuvers++;
    if (adv.type === "speed") give.speedFactor = 0.65;
    else if (adv.type === "vertical") give.altTarget = give.alt + adv.dAlt;
    else give.crossTarget = sep.daa_hmd_m * 1.1; // turn right, open ~165 m
  }
  // clear conflict highlight on agents no longer maneuvering
  for (const ag of sim.agents) if (!ag.maneuver) ag.conflictColor = false;

  return conflicts;
}

// Live view model for the map (lat/lng + status).
export function viewModel(sim) {
  return sim.agents
    .filter((a) => a.airborne)
    .map((a) => ({
      id: a.id, color: a.intruder ? "#ef4444" : a.color, name: a.name,
      intruder: a.intruder, maneuvering: !!a.maneuver, alt: a.alt,
      ...toLatLng(a.pos, sim.ref),
      heading: (Math.atan2(a.vel.x, a.vel.y) * 180) / Math.PI,
    }));
}

// Spawn a non-cooperative intruder on a converging course with a random
// airborne cooperative agent — the live "inject a conflict" wow moment.
export function injectConflict(sim, sep = SEP) {
  const targets = sim.agents.filter((a) => a.airborne && a.cooperative && !a.done);
  if (!targets.length) return false;
  const T = targets[Math.floor(Math.random() * targets.length)];
  const dir = unit(T.vel.x || T.vel.y ? T.vel : T.dir);
  const lead = 1400; // m ahead
  const start = { x: T.pos.x + dir.x * lead, y: T.pos.y + dir.y * lead };
  const heading = { x: -dir.x, y: -dir.y }; // head-on toward T
  const speed = 45;
  const id = 10000 + sim.agents.length;
  const intruder = {
    id, color: "#ef4444", name: "Non-cooperative intruder",
    priority: -1, cooperative: false, intruder: true,
    a: start, b: { x: start.x + heading.x * 6000, y: start.y + heading.y * 6000 },
    dir: heading, legLen: 6000, speed, climb: 3,
    dep: sim.t, layer: T.alt,
    s: 0, cross: 0, crossTarget: 0, alt: T.alt, altTarget: T.alt, speedFactor: 1,
    maneuver: null, pos: { ...start }, prevPos: { ...start },
    vel: { x: heading.x * speed, y: heading.y * speed },
    airborne: true, done: false,
  };
  sim.agents.push(intruder);
  return true;
}
