// Circular-orbit propagation with J2 nodal precession.
//
// MODEL SCOPE (disclosed): circular orbits only (e = 0), two-body motion plus
// the secular J2 effect on the right ascension of the ascending node. No drag,
// no SRP, no third-body, no station-keeping, no TLE ingest. For coverage
// geometry over hours-to-days this is the standard first-order model — J2 nodal
// regression is the dominant secular term and is what makes sun-synchronous
// orbits work, so it is included rather than ignored.

import { MU, R_EARTH, J2, OMEGA_EARTH, SOLAR_YEAR_S, D2R, R2D } from "../data/constants.js";

// Semi-major axis from altitude above the equatorial radius.
export const aFromAlt = (alt_km) => R_EARTH + alt_km;

// Mean motion n = sqrt(mu / a^3)  [rad/s]
export const meanMotion = (a_km) => Math.sqrt(MU / (a_km * a_km * a_km));

// Keplerian orbital period T = 2*pi*sqrt(a^3/mu)  [s]
export const period = (a_km) => 2 * Math.PI * Math.sqrt((a_km * a_km * a_km) / MU);

// Secular J2 nodal precession rate for a circular orbit [rad/s]:
//   dOmega/dt = -3/2 * J2 * (Re/a)^2 * n * cos(i)
export function nodalPrecession(a_km, inc_deg) {
  const n = meanMotion(a_km);
  const ratio = R_EARTH / a_km;
  return -1.5 * J2 * ratio * ratio * n * Math.cos(inc_deg * D2R);
}

// Sun-synchronous inclination: the inclination whose nodal precession matches
// the mean motion of the Earth about the Sun (360° per tropical year).
export function sunSyncInclination(alt_km) {
  const a = aFromAlt(alt_km);
  const n = meanMotion(a);
  const ratio = R_EARTH / a;
  const targetRate = (2 * Math.PI) / SOLAR_YEAR_S; // +0.9856 deg/day
  // targetRate = -1.5 J2 (Re/a)^2 n cos(i)  =>  cos(i) = -targetRate/(1.5 J2 (Re/a)^2 n)
  const cosI = -targetRate / (1.5 * J2 * ratio * ratio * n);
  if (cosI < -1 || cosI > 1) return null; // no SSO solution at this altitude
  return Math.acos(cosI) * R2D;
}

// Altitude of a circular orbit with a given period (inverse of `period`).
export function altFromPeriod(T_s) {
  const a = Math.cbrt((MU * T_s * T_s) / (4 * Math.PI * Math.PI));
  return a - R_EARTH;
}

// Propagate one circular satellite to time t (seconds since epoch) and return
// its sub-satellite geodetic-ish point (spherical Earth) in degrees.
//
// Elements: a (km), inc (deg), raan0 (deg), u0 (deg argument of latitude).
// ECI position for a circular orbit:
//   x = a(cos u cos O - sin u cos i sin O)
//   y = a(cos u sin O + sin u cos i cos O)
//   z = a sin u sin i
// Sub-satellite longitude is the ECI longitude minus Earth rotation. We take
// GMST = 0 at t = 0 (epoch-relative), which is honest for coverage statistics
// (they are rotation-invariant) but means longitudes are NOT absolute.
export function subPoint(sat, t) {
  const { a, inc, raan0, u0 } = sat;
  const n = meanMotion(a);
  const O = (raan0 * D2R) + nodalPrecession(a, inc) * t;
  const u = (u0 * D2R) + n * t;
  const ci = Math.cos(inc * D2R), si = Math.sin(inc * D2R);
  const cu = Math.cos(u), su = Math.sin(u);
  const x = a * (cu * Math.cos(O) - su * ci * Math.sin(O));
  const y = a * (cu * Math.sin(O) + su * ci * Math.cos(O));
  const z = a * su * si;
  const r = Math.hypot(x, y, z);
  const lat = Math.asin(z / r) * R2D;
  let lon = (Math.atan2(y, x) - OMEGA_EARTH * t) * R2D;
  lon = ((((lon + 180) % 360) + 360) % 360) - 180; // wrap to [-180, 180)
  return { lat, lon, alt: r - R_EARTH };
}

// Earth-central half-angle of the visibility footprint for a satellite at
// altitude h seen at minimum elevation angle eps:
//   lambda = acos( (Re/(Re+h)) * cos(eps) ) - eps
// At eps = 0 this reduces to the horizon-limited acos(Re/(Re+h)).
export function footprintHalfAngle(alt_km, minElev_deg) {
  const e = minElev_deg * D2R;
  const ratio = R_EARTH / (R_EARTH + alt_km);
  const v = ratio * Math.cos(e);
  if (v > 1) return 0;
  return Math.acos(v) - e; // radians
}

// Ground radius of that footprint along the Earth's surface [km].
export const footprintRadiusKm = (alt_km, minElev_deg) =>
  footprintHalfAngle(alt_km, minElev_deg) * R_EARTH;

// Great-circle central angle between two lat/lon points [radians].
export function centralAngle(lat1, lon1, lat2, lon2) {
  const p1 = lat1 * D2R, p2 = lat2 * D2R;
  const dp = (lat2 - lat1) * D2R, dl = (lon2 - lon1) * D2R;
  const s = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * Math.asin(Math.min(1, Math.sqrt(s)));
}
