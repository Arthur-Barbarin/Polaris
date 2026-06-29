// Numerical verification script. Run with: `node verify.mjs`
// Intended for review by an aerospace / drone-ops expert: every number
// the UI displays can be reconstructed and audited here against
// published manufacturer specs and FAA rule text.

import { DRONES } from "./src/data/drones.js";
import {
  missionEnergy,
  headwindComponent,
  pathBearing,
  avgPowerW,
  maxRangeM,
} from "./src/models/energy.js";
import { planRoute, pathDistance_m, haversine_m } from "./src/models/planner.js";
import { riskExposure, popDensity } from "./src/models/risk.js";
import { checkCompliance } from "./src/models/regulatory.js";
import { NO_FLY_PRESETS } from "./src/data/no_fly.js";

const fmt = (x, n = 1) => (x == null ? "—" : Number(x).toFixed(n));
const line = (label, v) => console.log(label.padEnd(48), v);

console.log("\n=== 1. Empirical power & range (from published endurance) ===");
console.log("Sanity check: multirotors typically 80–100 W/kg (Mavic 3 ≈95).");
for (const d of Object.values(DRONES)) {
  const P = avgPowerW(d);
  const rng = maxRangeM(d) / 1000;
  const wkg = P ? (P / d.mtow_kg).toFixed(1) : "—";
  line(
    `${d.name.padEnd(22)} P̄=${fmt(P, 0).padStart(4)} W   rng=${fmt(rng, 1).padStart(5)} km   ${wkg} W/kg`,
    ""
  );
}

console.log("\n=== 2. Wind decomposition (5 m/s reference wind) ===");
const tests = [
  { wf: 270, br: 90, exp: -5, note: "W wind, E flight → tailwind" },
  { wf: 90, br: 90, exp: 5, note: "E wind, E flight → headwind" },
  { wf: 0, br: 90, exp: 0, note: "N wind, E flight → crosswind" },
  { wf: 180, br: 90, exp: 0, note: "S wind, E flight → crosswind" },
  { wf: 45, br: 90, exp: 3.54, note: "NE wind, E flight" },
];
for (const t of tests) {
  const h = headwindComponent(5, t.wf, t.br);
  const ok = Math.abs(h - t.exp) < 0.05 ? "✓" : "✗";
  line(`${ok} ${t.note}: expect ${t.exp}`, fmt(h, 2));
}

console.log("\n=== 3. Default mission: Seattle Center → Bellevue Square ===");
const start = { lat: 47.6205, lng: -122.3493 };
const goal = { lat: 47.6172, lng: -122.2017 };
const hav = haversine_m(start, goal);
const plan = planRoute({ start, goal, noFlyPolys: [] });
const pathD = pathDistance_m(plan.path);
line("Haversine distance:", `${fmt(hav / 1000, 2)} km`);
line("Bearing:", `${fmt(pathBearing(start, goal), 0)}°`);
line("A* path distance:", `${fmt(pathD / 1000, 2)} km (${fmt(pathD / hav, 2)}× haversine)`);
line("Nodes expanded:", plan.nodesExpanded);
const e0 = missionEnergy(DRONES.skydio_x10, pathD, 0, 0);
line("Skydio X10 still-air energy:", `${fmt(e0.energy_wh, 1)} Wh of ${fmt(e0.energy_available_wh, 1)} usable (margin ${fmt(e0.margin_pct, 0)}%)`);

console.log("\n=== 4. Headwind sensitivity sweep (Skydio X10, same distance) ===");
for (const h of [-10, -5, 0, 5, 10, 12]) {
  const e = missionEnergy(DRONES.skydio_x10, pathD, h, 0);
  line(
    `headwind ${h.toString().padStart(3)} m/s`,
    `gs=${fmt(e.ground_speed_ms, 1)} m/s · t=${fmt(e.time_s / 60, 1)} min · E=${fmt(e.energy_wh, 1)} Wh · feasible=${e.feasible}`
  );
}

console.log("\n=== 5. Regulatory compliance matrix ===");
const sc = [
  { name: "Skydio VLOS day Class G", drone: DRONES.skydio_x10, vlos: true, controlled: false, overPeople: false, night: false, alt: 250 },
  { name: "Skydio BVLOS day Class G", drone: DRONES.skydio_x10, vlos: false, controlled: false, overPeople: false, night: false, alt: 250 },
  { name: "Wing BVLOS day Class G (over people)", drone: DRONES.wing_hb, vlos: false, controlled: false, overPeople: true, night: false, alt: 150 },
  { name: "Skydio VLOS night Class D", drone: DRONES.skydio_x10, vlos: true, controlled: true, overPeople: false, night: true, alt: 350 },
  { name: "Zipline P2 BVLOS day Class G", drone: DRONES.zipline_p2, vlos: false, controlled: false, overPeople: true, night: false, alt: 300 },
  { name: "Skydio VLOS 450 ft (above 400 ft)", drone: DRONES.skydio_x10, vlos: true, controlled: false, overPeople: false, night: false, alt: 450 },
];
for (const s of sc) {
  const r = checkCompliance({
    drone: s.drone, max_altitude_ft: s.alt,
    vlos: s.vlos, controlled_airspace: s.controlled,
    over_people: s.overPeople, night: s.night,
  });
  line(s.name, r.allow ? "ALLOW" : "BLOCK");
  for (const f of r.findings.filter(f => f.level === "block")) line("    ⛔", f.text);
}

console.log("\n=== 6. No-fly detour ===");
const ksea = NO_FLY_PRESETS.find(p => p.id === "ksea").polygon;
const kbfi = NO_FLY_PRESETS.find(p => p.id === "kbfi").polygon;
const s2 = { lat: 47.62, lng: -122.32 };
const g2 = { lat: 47.39, lng: -122.32 };
const havS = haversine_m(s2, g2);
const free = planRoute({ start: s2, goal: g2, noFlyPolys: [] });
const block = planRoute({ start: s2, goal: g2, noFlyPolys: [ksea, kbfi] });
line("Haversine (north→south):", `${fmt(havS / 1000, 2)} km`);
line("A* no NFZ:", `${fmt(pathDistance_m(free.path) / 1000, 2)} km`);
line("A* KSEA+KBFI in path:", `${fmt(pathDistance_m(block.path) / 1000, 2)} km (detour ${fmt(pathDistance_m(block.path) / pathDistance_m(free.path), 2)}×)`);

console.log("\n=== 7. Population density spot checks ===");
line("Downtown Seattle (47.61, -122.33):", fmt(popDensity({ lat: 47.6062, lng: -122.3321 }), 1));
line("Bellevue (47.61, -122.20):", fmt(popDensity({ lat: 47.6101, lng: -122.2015 }), 1));
line("Mid Lake Washington:", fmt(popDensity({ lat: 47.61, lng: -122.27 }), 1));
line("Rural (Olympia):", fmt(popDensity({ lat: 47.04, lng: -122.9 }), 1));
const re = riskExposure(plan.path);
line("Default route exposure:", `mean ${fmt(re.mean, 2)}, peak ${fmt(re.peak, 2)}, class ${re.class}`);
