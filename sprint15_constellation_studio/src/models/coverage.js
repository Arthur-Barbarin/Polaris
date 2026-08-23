// Coverage & revisit analysis.
//
// Instantaneous coverage: lay an equal-angle lat/lon grid over the globe and
// mark a cell covered if ANY satellite's sub-point is within the footprint
// half-angle. Cells are AREA-WEIGHTED by cos(latitude) — an unweighted cell
// count would massively over-credit the poles (a 2°x2° cell at 80°N has ~17%
// of the area of one at the equator). This is the single most common error in
// naive coverage estimates, so it is done correctly here and verified.
//
// Site revisit: propagate over a time span and record, for one ground site,
// the intervals during which at least one satellite is in view. From those we
// derive coverage fraction, maximum gap, and mean revisit interval.

import { subPoint, footprintHalfAngle, centralAngle } from "./orbit.js";
import { D2R } from "../data/constants.js";

// Sub-points of every satellite at time t.
export const propagate = (sats, t) => sats.map((s) => ({ ...subPoint(s, t), id: s.id, plane: s.plane }));

// Area-weighted instantaneous coverage fraction over the whole globe.
// gridStep_deg trades accuracy for speed; 4° is plenty for a live UI.
export function instantCoverage(subPoints, halfAngle_rad, gridStep_deg = 4) {
  let covered = 0, total = 0;
  for (let lat = -90 + gridStep_deg / 2; lat < 90; lat += gridStep_deg) {
    const w = Math.cos(lat * D2R); // area weight
    for (let lon = -180 + gridStep_deg / 2; lon < 180; lon += gridStep_deg) {
      total += w;
      for (let k = 0; k < subPoints.length; k++) {
        const sp = subPoints[k];
        if (Math.abs(sp.lat - lat) * D2R > halfAngle_rad) continue; // cheap reject
        if (centralAngle(lat, lon, sp.lat, sp.lon) <= halfAngle_rad) { covered += w; break; }
      }
    }
  }
  return total > 0 ? covered / total : 0;
}

// Coverage fraction restricted to a latitude band — reveals why a 53°
// constellation leaves the poles uncovered.
export function coverageByLatBand(subPoints, halfAngle_rad, gridStep_deg = 4) {
  const bands = [];
  for (let lat0 = -90; lat0 < 90; lat0 += 10) {
    let covered = 0, total = 0;
    for (let lat = lat0 + gridStep_deg / 2; lat < lat0 + 10; lat += gridStep_deg) {
      const w = Math.cos(lat * D2R);
      for (let lon = -180 + gridStep_deg / 2; lon < 180; lon += gridStep_deg) {
        total += w;
        for (let k = 0; k < subPoints.length; k++) {
          const sp = subPoints[k];
          if (Math.abs(sp.lat - lat) * D2R > halfAngle_rad) continue;
          if (centralAngle(lat, lon, sp.lat, sp.lon) <= halfAngle_rad) { covered += w; break; }
        }
      }
    }
    bands.push({ lat: lat0 + 5, coverage: total > 0 ? covered / total : 0 });
  }
  return bands;
}

// How many satellites are in view of one site right now.
export function satsInView(subPoints, site, halfAngle_rad) {
  let n = 0;
  for (const sp of subPoints)
    if (centralAngle(site.lat, site.lng, sp.lat, sp.lon) <= halfAngle_rad) n++;
  return n;
}

// Revisit / gap statistics for one ground site over `span_s` seconds.
// Returns coverage fraction, longest gap, mean gap, and number of passes.
export function siteRevisit(sats, site, halfAngle_rad, span_s = 86400, dt_s = 30) {
  let coveredSteps = 0, steps = 0;
  let gaps = [], curGap = 0, passes = 0, wasCovered = false;
  let maxInView = 0;

  for (let t = 0; t < span_s; t += dt_s) {
    steps++;
    let inView = 0;
    for (const s of sats) {
      const sp = subPoint(s, t);
      if (centralAngle(site.lat, site.lng, sp.lat, sp.lon) <= halfAngle_rad) inView++;
    }
    if (inView > maxInView) maxInView = inView;
    const covered = inView > 0;
    if (covered) {
      coveredSteps++;
      if (curGap > 0) { gaps.push(curGap * dt_s); curGap = 0; }
      if (!wasCovered) passes++;
    } else {
      curGap++;
    }
    wasCovered = covered;
  }
  if (curGap > 0) gaps.push(curGap * dt_s);

  const maxGap_s = gaps.length ? Math.max(...gaps) : 0;
  const meanGap_s = gaps.length ? gaps.reduce((a, b) => a + b, 0) / gaps.length : 0;
  return {
    coverageFrac: steps ? coveredSteps / steps : 0,
    maxGap_s, meanGap_s, passes, maxInView,
    continuous: maxGap_s === 0,
  };
}

// Sweep constellation size and record global coverage — the "scale it" chart.
// For each size we average instantaneous coverage over a few epochs so the
// number isn't an artefact of one lucky snapshot.
export function coverageSweep(buildFn, sizes, alt_km, minElev_deg, samples = 4, period_s = 6000) {
  const half = footprintHalfAngle(alt_km, minElev_deg);
  return sizes.map(({ planes, satsPerPlane }) => {
    const sats = buildFn(planes, satsPerPlane);
    let sum = 0;
    for (let k = 0; k < samples; k++) {
      const t = (k * period_s) / samples;
      sum += instantCoverage(propagate(sats, t), half, 5);
    }
    return { n: planes * satsPerPlane, planes, satsPerPlane, coverage: (sum / samples) * 100 };
  });
}
