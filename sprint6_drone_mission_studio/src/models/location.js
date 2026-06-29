// Endpoint validation and corridor-blocker identification.
import { pointInPolygon } from "./planner.js";

// Returns the first named zone that contains `pt`, or null.
export function findContainingZone(pt, zones) {
  for (const z of zones) {
    if (pointInPolygon(pt, z.polygon)) return z;
  }
  return null;
}

// Hard validation — only blocks regulated airspace. Water is checked
// asynchronously via Nominatim (see checkOverWater) and surfaces as a
// soft warning, not a block, because drone operations from boats and
// fixed water platforms are legitimate.
export function validateLocation(pt, noFlyZones) {
  const nf = findContainingZone(pt, noFlyZones);
  if (nf) return { ok: false, type: "restricted", name: nf.name };
  return { ok: true };
}

// Reverse-geocode against OpenStreetMap Nominatim to determine whether a
// click landed over a named body of water. Soft check (warning only).
//
// Nominatim policy: ≤1 request/second, attach an identifying User-Agent
// (browser-set in this case), no heavy automated use. Suitable for
// interactive map clicks. https://operations.osmfoundation.org/policies/nominatim/
//
// The endpoint is anonymous — no API key. Returns { water, name } or
// { water: false } on land / on error (we fail open — better to miss a
// warning than to fabricate one).
const WATER_CLASSES = new Set(["water", "waterway"]);
const WATER_TYPES = new Set([
  "water", "bay", "strait", "sea", "ocean",
  "river", "stream", "canal", "lake", "reservoir", "pond",
]);

export async function checkOverWater(point, { signal } = {}) {
  const url =
    "https://nominatim.openstreetmap.org/reverse" +
    `?lat=${point.lat.toFixed(5)}&lon=${point.lng.toFixed(5)}` +
    "&format=json&zoom=14&addressdetails=0";
  try {
    const r = await fetch(url, {
      headers: { Accept: "application/json" },
      signal,
    });
    if (!r.ok) return { water: false };
    const j = await r.json();
    const cls = j.class;
    const type = j.type;
    const isWater =
      WATER_CLASSES.has(cls) ||
      (cls === "natural" && WATER_TYPES.has(type));
    if (!isWater) return { water: false };
    // Try to pick a friendly name (first comma-segment of display_name,
    // falling back to "water").
    const name =
      (j.display_name && j.display_name.split(",")[0].trim()) ||
      type ||
      "water";
    return { water: true, name };
  } catch {
    return { water: false };
  }
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
