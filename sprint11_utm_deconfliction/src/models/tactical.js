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
// first that restores well clear when re-simulated against the intruder:
//   1) speed brake (reduce ground speed),
//   2) vertical maneuver (climb/descend one layer),
//   3) horizontal offset (turn right — mirrors VFR right-of-way convention).

import { cpaHoriz, tauMod, norm } from "./geo.js";
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

  // 1) Horizontal offset (visible on the map, mirrors VFR right-of-way):
  // search right turns until the predicted HMD recovers.
  for (const deg of [20, 30, 45, 60, 75]) {
    const turned = rot(give.vel, deg);
    if (trialHmd(give.pos, turned, keep) >= sep.daa_hmd_m)
      return { type: "heading", vel: turned, ok: true };
  }

  // 2) Vertical: step one layer away from the intruder.
  const dAlt = give.alt <= keep.alt ? -sep.daa_vert_m : sep.daa_vert_m;
  if (Math.abs(give.alt + dAlt - keep.alt) >= sep.daa_vert_m)
    return { type: "vertical", dAlt, vel: give.vel, ok: true };

  // 3) Speed brake as a last resort.
  const braked = { x: dir.x * speed * 0.6, y: dir.y * speed * 0.6 };
  if (trialHmd(give.pos, braked, keep) >= sep.daa_hmd_m)
    return { type: "speed", vel: braked, ok: true };

  // Fallback: hardest turn even if it doesn't fully clear.
  return { type: "heading", vel: rot(give.vel, 75), ok: false };
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
