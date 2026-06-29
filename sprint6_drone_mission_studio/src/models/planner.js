// A* path planner on a regular lat/lng grid clipped to the start/goal bbox.
//
// Cell cost = step distance × (1 + α · pop_density/10) + β · pop_density
// 8-connected neighbours. Heuristic = great-circle distance to goal
// (admissible — never overestimates real-world distance).
//
// No-fly polygons are hard-blocked (cells inside have cost = ∞ and are skipped).
// Default grid is 60×60 over a ~0.1° bbox padding → cell size on the order of
// 200 m at Seattle latitude, which is well below typical no-fly polygon detail.

import { popDensity } from "./risk.js";

export function haversine_m(a, b) {
  const R = 6371000;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const x =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((a.lat * Math.PI) / 180) *
      Math.cos((b.lat * Math.PI) / 180) *
      Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
}

export function pointInPolygon(pt, poly) {
  // Ray casting. poly = [{lat,lng},...]
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i].lng,
      yi = poly[i].lat;
    const xj = poly[j].lng,
      yj = poly[j].lat;
    const intersect =
      yi > pt.lat !== yj > pt.lat &&
      pt.lng < ((xj - xi) * (pt.lat - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

// Simple binary heap priority queue keyed on .f
class MinHeap {
  constructor() {
    this.h = [];
  }
  push(x) {
    this.h.push(x);
    this._up(this.h.length - 1);
  }
  pop() {
    const top = this.h[0];
    const last = this.h.pop();
    if (this.h.length) {
      this.h[0] = last;
      this._down(0);
    }
    return top;
  }
  size() {
    return this.h.length;
  }
  _up(i) {
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (this.h[p].f <= this.h[i].f) break;
      [this.h[p], this.h[i]] = [this.h[i], this.h[p]];
      i = p;
    }
  }
  _down(i) {
    const n = this.h.length;
    while (true) {
      const l = 2 * i + 1,
        r = 2 * i + 2;
      let s = i;
      if (l < n && this.h[l].f < this.h[s].f) s = l;
      if (r < n && this.h[r].f < this.h[s].f) s = r;
      if (s === i) break;
      [this.h[s], this.h[i]] = [this.h[i], this.h[s]];
      i = s;
    }
  }
}

export function planRoute({
  start,
  goal,
  noFlyPolys = [],
  gridN = null,    // if null, auto-pick to keep cell size ~250 m
  riskWeight = 80, // metres of detour the planner will accept per unit density (0–10)
  padDeg = 0.05,
  targetCell_m = 250,
  maxGridN = 140,
  minGridN = 50,
}) {
  // Bbox: start/goal + padDeg, then expanded to include any no-fly polygon
  // that actually overlaps the corridor (so A* has room to detour around it).
  // We don't include polygons that are far from the corridor — they'd just
  // coarsen the grid for no benefit.
  let minLat = Math.min(start.lat, goal.lat) - padDeg;
  let maxLat = Math.max(start.lat, goal.lat) + padDeg;
  let minLng = Math.min(start.lng, goal.lng) - padDeg;
  let maxLng = Math.max(start.lng, goal.lng) + padDeg;
  for (const poly of noFlyPolys) {
    let pMinLat = Infinity, pMaxLat = -Infinity,
        pMinLng = Infinity, pMaxLng = -Infinity;
    for (const p of poly) {
      if (p.lat < pMinLat) pMinLat = p.lat;
      if (p.lat > pMaxLat) pMaxLat = p.lat;
      if (p.lng < pMinLng) pMinLng = p.lng;
      if (p.lng > pMaxLng) pMaxLng = p.lng;
    }
    // Only expand bbox if the polygon overlaps current bbox.
    const overlaps =
      pMaxLat >= minLat && pMinLat <= maxLat &&
      pMaxLng >= minLng && pMinLng <= maxLng;
    if (overlaps) {
      minLat = Math.min(minLat, pMinLat - padDeg);
      maxLat = Math.max(maxLat, pMaxLat + padDeg);
      minLng = Math.min(minLng, pMinLng - padDeg);
      maxLng = Math.max(maxLng, pMaxLng + padDeg);
    }
  }

  // Auto grid size: pick so cell diagonal ≈ targetCell_m.
  if (gridN == null) {
    const latM = (maxLat - minLat) * 111_000;
    const lngM = (maxLng - minLng) * 111_000 * Math.cos((minLat + maxLat) * Math.PI / 360);
    const span = Math.max(latM, lngM);
    gridN = Math.max(minGridN, Math.min(maxGridN, Math.round(span / targetCell_m)));
  }
  const dLat = (maxLat - minLat) / gridN;
  const dLng = (maxLng - minLng) / gridN;
  const W = gridN + 1;

  const toCell = (p) => ({
    r: Math.max(0, Math.min(gridN, Math.round((p.lat - minLat) / dLat))),
    c: Math.max(0, Math.min(gridN, Math.round((p.lng - minLng) / dLng))),
  });
  const toLatLng = (r, c) => ({
    lat: minLat + r * dLat,
    lng: minLng + c * dLng,
  });
  const key = (r, c) => r * W + c;

  const startCell = toCell(start);
  const goalCell = toCell(goal);
  const startKey = key(startCell.r, startCell.c);
  const goalKey = key(goalCell.r, goalCell.c);

  // Precompute no-fly mask
  const blocked = new Uint8Array(W * W);
  for (let r = 0; r <= gridN; r++) {
    for (let c = 0; c <= gridN; c++) {
      const p = toLatLng(r, c);
      for (const poly of noFlyPolys) {
        if (pointInPolygon(p, poly)) {
          blocked[key(r, c)] = 1;
          break;
        }
      }
    }
  }
  // Always allow start & goal (drone has to depart and land)
  blocked[startKey] = 0;
  blocked[goalKey] = 0;

  const gScore = new Map();
  const cameFrom = new Map();
  gScore.set(startKey, 0);

  const open = new MinHeap();
  open.push({
    key: startKey,
    r: startCell.r,
    c: startCell.c,
    f: haversine_m(start, goal),
  });

  const dirs = [
    [-1, 0], [1, 0], [0, -1], [0, 1],
    [-1, -1], [-1, 1], [1, -1], [1, 1],
  ];

  let nodesExpanded = 0;
  while (open.size() > 0) {
    const cur = open.pop();
    nodesExpanded++;
    if (cur.key === goalKey) {
      const path = [];
      let k = cur.key;
      while (k !== undefined) {
        const r = Math.floor(k / W);
        const c = k % W;
        path.unshift(toLatLng(r, c));
        k = cameFrom.get(k);
      }
      return { path, found: true, nodesExpanded };
    }
    const curG = gScore.get(cur.key);
    for (const [dr, dc] of dirs) {
      const nr = cur.r + dr,
        nc = cur.c + dc;
      if (nr < 0 || nr > gridN || nc < 0 || nc > gridN) continue;
      const nk = key(nr, nc);
      if (blocked[nk]) continue;
      const a = toLatLng(cur.r, cur.c);
      const b = toLatLng(nr, nc);
      const stepDist = haversine_m(a, b);
      const cellRisk = popDensity(b); // 0–10
      const stepCost = stepDist * (1 + cellRisk / 10) + riskWeight * cellRisk;
      const tentativeG = curG + stepCost;
      if (tentativeG < (gScore.get(nk) ?? Infinity)) {
        gScore.set(nk, tentativeG);
        cameFrom.set(nk, cur.key);
        const h = haversine_m(b, goal);
        open.push({ key: nk, r: nr, c: nc, f: tentativeG + h });
      }
    }
  }
  return { path: [], found: false, nodesExpanded };
}

export function pathDistance_m(path) {
  let d = 0;
  for (let i = 1; i < path.length; i++) d += haversine_m(path[i - 1], path[i]);
  return d;
}
