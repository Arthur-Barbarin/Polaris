// Tactical (in-flight) detect-and-avoid.
//
// Every simulation step we test each airborne pair for a predicted loss of
// "well clear", using the DO-365 (RTCA SC-228) formulation: a violation is
// predicted when, at the closest point of approach, the horizontal miss
// distance (HMD) is below threshold AND the vertical separation is below
// threshold AND the modified time-to-CPA (tau) is below threshold, while the
// pair is closing. This is a simplified GEOMETRIC well-clear test — it is NOT
// the ACAS-Xu / DO-386 optimised lookup-table logic, which we don't claim.
//
// When a conflict is predicted, the lower-priority ("give-way") vehicle gets a
// resolution advisory. We search a small, ordered maneuver set and pick the
// first that restores well clear when re-simulated against the intruder, in
// order of increasing intrusiveness:
//   1) horizontal offset (smallest right turn that works — mirrors the VFR
//      right-of-way convention),
//   2) vertical maneuver (climb/descend one layer),
//   3) speed brake (last resort).
//
// A resolution is NOT free. The horizontal advisory carries the turn angle it
// was selected for, and the simulator opens lateral separation at the rate that
// angle actually produces (speed * sin(angle), capped by the airframe's lateral
// rate limit). The vertical advisory is only offered when the vehicle's climb
// rate can actually build the vertical threshold before the closest point of
// approach. Both gates are what give the demo a computable recovery envelope.

import { cpaHoriz, tauMod, norm } from "./geo.js";
import { TACT } from "../data/airspace.js";
import { SEP } from "../data/airspace.js";

const rot = (v, deg) => {
  const a = (deg * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
  return { x: v.x * c - v.y * s, y: v.x * s + v.y * c };
};

// Predict the pair outcome given current states. Vertical separation is taken
// as the current level-flight altitude difference (climb legs are transient).
export function predictPair(A, B, sep = SEP) {
  const c = cpaHoriz(A.pos, A.vel, B.pos, B.vel);
  const tau = tauMod(A.pos, A.vel, B.pos, B.vel, sep.daa_hmd_m);
  const vert = Math.abs(A.alt - B.alt);
  const wellClearViolation =
    c.closing && c.hmd < sep.daa_hmd_m && vert < sep.daa_vert_m && tau < sep.daa_tau_s;
  const curHoriz = c.r0;
  const los = curHoriz < sep.los_horiz_m && vert < sep.los_vert_m;
  return { ...c, tau, vert, wellClearViolation, los, curHoriz };
}

// Predicted HMD if `own` flew with a trial velocity against a fixed intruder.
function trialHmd(ownPos, trialVel, other) {
  return cpaHoriz(ownPos, trialVel, other.pos, other.vel).hmd;
}

// Build an ordered resolution advisory for the give-way vehicle in a conflict.
// Returns { type, vel?, dAlt?, ok } — ok=false means no maneuver in the set
// restored well clear (the residual near-miss the metrics will count).
export function resolve(give, keep, sep = SEP) {
  const speed = norm(give.vel) || give.speed || 1;
  const dir = { x: give.vel.x / speed, y: give.vel.y / speed };

  // Time available before the closest point of approach — every gate below is
  // measured against it, minus the detect-and-commit latency.
  const t_cpa = cpaHoriz(give.pos, give.vel, keep.pos, keep.vel).t_cpa;
  const t_avail = t_cpa - TACT.react_s;

  // 1) Horizontal offset (least intrusive, visible on the map): the smallest
  // right turn that both restores the predicted HMD AND can physically open
  // the required lateral separation in the time left.
  const needLateral = sep.daa_hmd_m * 1.15;
  for (const deg of [20, 30, 45, 60, 75]) {
    const turned = rot(give.vel, deg);
    if (trialHmd(give.pos, turned, keep) < sep.daa_hmd_m) continue;
    // Lateral opening rate this turn actually produces, capped by the airframe.
    const latRate = Math.min(TACT.lat_rate_ms, speed * Math.sin((deg * Math.PI) / 180));
    if (latRate * t_avail < needLateral) continue;   // cannot finish in time
    return { type: "heading", deg, latRate, vel: turned, ok: true };
  }

  // 2) Vertical: step one full LAYER away (`strat_vert_m`), not exactly the DAA
  // threshold. A 30 m step left the aircraft sitting precisely on
  // `vert < daa_vert_m`, a strict inequality, so the encounter came out
  // "resolved" with 30 m of horizontal separation and 30 m of vertical — safe
  // by the letter of the test and on its knife edge. One layer is 45 m and
  // clears the threshold with margin. Offered only if the climb rate can build
  // it before CPA.
  const climb = give.climb ?? 0;
  const step = sep.strat_vert_m;
  const dAlt = give.alt <= keep.alt ? -step : step;
  const vertNeeded = Math.abs(give.alt + dAlt - keep.alt);
  if (vertNeeded >= sep.daa_vert_m && climb * t_avail >= step)
    return { type: "vertical", dAlt, vel: give.vel, ok: true };

  // 3) Speed brake as a last resort (65% of ground speed).
  const braked = { x: dir.x * speed * 0.65, y: dir.y * speed * 0.65 };
  if (trialHmd(give.pos, braked, keep) >= sep.daa_hmd_m)
    return { type: "speed", vel: braked, ok: true };

  // Nothing in the set can recover in the time available: fly the hardest turn
  // anyway and let the encounter be scored for what it is.
  const deg = 75;
  return {
    type: "heading", deg,
    latRate: Math.min(TACT.lat_rate_ms, speed * Math.sin((deg * Math.PI) / 180)),
    vel: rot(give.vel, deg), ok: false,
  };
}

// Scan all airborne pairs. Returns predicted conflicts and current LoS events.
export function scan(agents, sep = SEP) {
  const conflicts = [];
  const losEvents = [];
  for (let i = 0; i < agents.length; i++) {
    for (let j = i + 1; j < agents.length; j++) {
      const A = agents[i], B = agents[j];
      if (!A.airborne || !B.airborne) continue;
      const p = predictPair(A, B, sep);
      if (p.los) losEvents.push({ i, j, ...p });
      if (p.wellClearViolation) {
        // give-way = higher id (deterministic, priority by earlier departure)
        const giveIsA = A.priority > B.priority;
        conflicts.push({ i, j, give: giveIsA ? i : j, keep: giveIsA ? j : i, ...p });
      }
    }
  }
  return { conflicts, losEvents };
}
