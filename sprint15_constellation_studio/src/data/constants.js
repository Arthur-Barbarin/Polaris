// Physical constants — all sourced, no tuned/fudge values.
//
// Sources:
//  - WGS-84 / EGM-96: Earth equatorial radius, gravitational parameter, J2.
//  - IERS: Earth sidereal rotation rate.

export const MU = 398600.4418;        // Earth gravitational parameter, km^3/s^2 (EGM-96)
export const R_EARTH = 6378.137;      // Earth equatorial radius, km (WGS-84)
export const J2 = 1.08262668e-3;      // Earth second zonal harmonic (WGS-84)
export const OMEGA_EARTH = 7.2921159e-5; // Earth sidereal rotation rate, rad/s (IERS)
export const SIDEREAL_DAY_S = 86164.0905; // s
export const SOLAR_YEAR_S = 365.2421897 * 86400; // s (mean tropical year)

export const D2R = Math.PI / 180;
export const R2D = 180 / Math.PI;
