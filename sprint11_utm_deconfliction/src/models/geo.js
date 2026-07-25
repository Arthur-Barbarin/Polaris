// Geometry & closest-point-of-approach (CPA) math.
//
// All conflict math is done in a local East-North-Up (ENU) frame in metres,
// obtained by an equirectangular projection about a reference point. Over the
// Paris metro area (< ~60 km) the equirectangular distortion is < 0.3%, which
// is negligible next to the 150 m separation buffers. Trajectories are
// straight great-circle-ish legs; we treat each leg as a straight line in ENU.

const R_EARTH = 6371008.8; // mean Earth radius, m (IUGG)
const D2R = Math.PI / 180;

// Project lat/lng -> local ENU metres about ref.
export function toENU(p, ref) {
  const x = (p.lng - ref.lng) * D2R * R_EARTH * Math.cos(ref.lat * D2R);
  const y = (p.lat - ref.lat) * D2R * R_EARTH;
  return { x, y };
}

// Inverse: ENU metres -> lat/lng.
export function toLatLng(e, ref) {
  const lat = ref.lat + (e.y / (D2R * R_EARTH));
  const lng = ref.lng + e.x / (D2R * R_EARTH * Math.cos(ref.lat * D2R));
  return { lat, lng };
}

export function haversine_m(a, b) {
  const dLat = (b.lat - a.lat) * D2R;
  const dLng = (b.lng - a.lng) * D2R;
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(a.lat * D2R) * Math.cos(b.lat * D2R) * Math.sin(dLng / 2) ** 2;
  return 2 * R_EARTH * Math.asin(Math.min(1, Math.sqrt(s)));
}

export const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y });
export const add = (a, b) => ({ x: a.x + b.x, y: a.y + b.y });
export const scale = (a, k) => ({ x: a.x * k, y: a.y * k });
export const dot = (a, b) => a.x * b.x + a.y * b.y;
export const norm = (a) => Math.hypot(a.x, a.y);

// Horizontal closest-point-of-approach between two vehicles moving at constant
// velocity. Positions p1,p2 (ENU m), velocities v1,v2 (m/s).
// Returns { t_cpa (s, >=0), hmd (m), r0 (current range, m), closing (bool) }.
export function cpaHoriz(p1, v1, p2, v2) {
  const r = sub(p1, p2); // relative position
  const v = sub(v1, v2); // relative velocity
  const vv = dot(v, v);
  const r0 = norm(r);
  let t = vv > 1e-9 ? -dot(r, v) / vv : 0;
  if (t < 0) t = 0; // CPA already passed -> current separation is closest ahead
  const rel = add(r, scale(v, t));
  return { t_cpa: t, hmd: norm(rel), r0, closing: dot(r, v) < 0 };
}

// Modified tau (DO-365 style) using a distance modification DMOD.
// tau_mod = (DMOD^2 - r^2) / (r * rdot), defined when closing (rdot < 0).
// Returns +Infinity when not closing.
export function tauMod(p1, v1, p2, v2, dmod) {
  const r = sub(p1, p2);
  const v = sub(v1, v2);
  const range = norm(r);
  if (range < 1e-6) return 0;
  const rdot = dot(r, v) / range; // range rate (negative when closing)
  if (rdot >= -1e-6) return Infinity;
  return (dmod * dmod - range * range) / (range * rdot);
}

// Deterministic PRNG (mulberry32) so every headline number is reproducible.
export function makeRng(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
