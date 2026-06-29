// Endpoint validation and corridor-blocker identification.
import { pointInPolygon } from "./planner.js";

// Returns the first named zone that contains `pt`, or null.
export function findContainingZone(pt, zones) {
  for (const z of zones) {
    if (pointInPolygon(pt, z.polygon)) return z;
  }
  return null;
}

// Validate a candidate start/goal click.
// - waterBodies, noFlyZones: arrays of { id, name, polygon }
// Returns { ok: true } or { ok: false, type, name } with type ∈ { water, restricted }.
export function validateLocation(pt, waterBodies, noFlyZones) {
  const w = findContainingZone(pt, waterBodies);
  if (w) return { ok: false, type: "water", name: w.name };
  const nf = findContainingZone(pt, noFlyZones);
  if (nf) return { ok: false, type: "restricted", name: nf.name };
  return { ok: true };
}

// Identify which named no-fly zones actually cut the straight-line corridor
// between start and goal. Used to explain a "no path" outcome with named
// reasons rather than a generic failure.
export function findCorridorBlockers(start, goal, noFlyZones, samples = 80) {
  const blockers = [];
  for (const z of noFlyZones) {
    let hit = false;
    for (let i = 0; i <= samples; i++) {
      const t = i / samples;
      const pt = {
        lat: start.lat + (goal.lat - start.lat) * t,
        lng: start.lng + (goal.lng - start.lng) * t,
      };
      if (pointInPolygon(pt, z.polygon)) {
        hit = true;
        break;
      }
    }
    if (hit) blockers.push(z);
  }
  return blockers;
}
