// Walker constellation generation.
//
// Walker notation i: T/P/F — T total satellites, P equally-spaced planes,
// F the inter-plane phasing factor (0 <= F <= P-1).
//
//   Walker DELTA: the P ascending nodes are spread over the full 360°.
//     Used by GPS, Galileo, Starlink.
//   Walker STAR: the nodes are spread over 180° (each plane's ascending and
//     descending halves cover opposite sides), which is what near-polar
//     constellations use. Used by Iridium and OneWeb.
//
// Within a plane the S = T/P satellites are equally spaced in argument of
// latitude; between planes they are offset by F * 360/T degrees.

import { aFromAlt } from "./orbit.js";

export function buildWalker({ alt_km, inc_deg, planes, satsPerPlane, pattern = "delta", phasing = 0 }) {
  const a = aFromAlt(alt_km);
  const T = planes * satsPerPlane;
  const raanSpan = pattern === "star" ? 180 : 360;
  const sats = [];
  for (let p = 0; p < planes; p++) {
    const raan0 = (p * raanSpan) / planes;
    for (let s = 0; s < satsPerPlane; s++) {
      const u0 = (s * 360) / satsPerPlane + (phasing * p * 360) / T;
      sats.push({
        id: `${p}-${s}`,
        plane: p,
        a,
        inc: inc_deg,
        raan0,
        u0: ((u0 % 360) + 360) % 360,
      });
    }
  }
  return sats;
}

// Total satellite count for a config.
export const totalSats = (c) => c.planes * c.satsPerPlane;
