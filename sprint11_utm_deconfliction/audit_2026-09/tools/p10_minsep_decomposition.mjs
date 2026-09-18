import { deconflict } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/strategic.js";
import { generateFleet } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/fleet.js";
import { buildSim, step } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/sim.js";
import { SEP } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/data/airspace.js";
import { sub, norm } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/geo.js";
const REF = { lat: 48.8566, lng: 2.3522 };

console.log("=== Que mesure vraiment la tuile MIN SEP ? (aucune injection) ===\n");
for (const n of [40, 100]) {
  const flights = generateFleet(n, 42, 600);
  const { assignments } = deconflict(flights, REF);
  const sim = buildSim(assignments, REF);
  let best = { slant: Infinity };
  let bestHoriz = Infinity, losReal = 0;
  for (let t = 0; t < 3500; t++) {
    step(sim, 1, SEP);
    for (let i = 0; i < sim.agents.length; i++)
      for (let j = i + 1; j < sim.agents.length; j++) {
        const A = sim.agents[i], B = sim.agents[j];
        if (!A.airborne || !B.airborne) continue;
        const h = norm(sub(A.pos, B.pos)), v = Math.abs(A.alt - B.alt);
        const slant = Math.hypot(h, v);
        if (slant < best.slant) best = { slant, h, v };
        if (h < bestHoriz) bestHoriz = h;
        if (h < SEP.los_horiz_m && v < SEP.los_vert_m) losReal++;
      }
    if (sim.agents.every(a => a.done || !a.airborne) && t > 100) break;
  }
  console.log(`N=${n}`);
  console.log(`  tuile MIN SEP affichee (slant) = ${sim.stats.minSep.toFixed(0)} m`);
  console.log(`  decomposition de ce minimum    : horizontal ${best.h.toFixed(0)} m, vertical ${best.v.toFixed(0)} m`);
  console.log(`  separation HORIZONTALE minimale reelle = ${bestHoriz.toFixed(0)} m`);
  console.log(`  vraies pertes de separation (h<${SEP.los_horiz_m} ET v<${SEP.los_vert_m}) = ${losReal}`);
  console.log(`  -> plancher LoS horizontal = ${SEP.los_horiz_m} m ; espacement des couches = ${SEP.strat_vert_m} m\n`);
}
