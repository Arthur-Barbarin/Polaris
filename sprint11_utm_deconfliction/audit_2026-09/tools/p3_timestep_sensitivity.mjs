import { deconflict } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/strategic.js";
import { generateFleet } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/fleet.js";
import { buildSim, step, injectConflict } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/sim.js";
import { SEP } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/data/airspace.js";
const REF = { lat: 48.8566, lng: 2.3522 };

// rendre l'injection deterministe : toujours la meme cible
Math.random = () => 0;

function runCase(popup, dt, warm = 200) {
  const flights = generateFleet(40, 42, 600);
  const { assignments } = deconflict(flights, REF);
  const sim = buildSim(assignments, REF);
  for (let t = 0; t < warm; t += 1) step(sim, 1, SEP);   // chauffe identique, dt=1
  const inj = injectConflict(sim, { rangeM: popup, speed: 55 }, SEP);
  if (!inj) return null;
  for (let k = 0; k < 400; k++) {
    step(sim, dt, SEP);
    if (sim.stats.last) break;
  }
  return sim.stats.last ? { ...sim.stats.last, tcpa: inj.tcpa } : null;
}

console.log("=== P3 : le verdict de securite depend-il du pas de temps ? ===");
console.log("(dt = 0.5 x le curseur 'Sim speed' de l'interface : 0.5 a 10 s)\n");
console.log("popup_m |  dt=0.5s      dt=1s        dt=3s(defaut) dt=5s        dt=10s(max)");
for (const popup of [300, 500, 600, 700, 900, 1200, 1600]) {
  let line = String(popup).padEnd(8) + "|";
  for (const dt of [0.5, 1, 3, 5, 10]) {
    const r = runCase(popup, dt);
    const s = r ? `${r.outcome === "LOSS OF SEP" ? "PERTE" : "ok"} ${r.minSep}m` : "n/a";
    line += "  " + s.padEnd(12);
  }
  console.log(line);
}
