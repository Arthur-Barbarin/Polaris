import { deconflict } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/strategic.js";
import { generateFleet } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/fleet.js";
import { buildSim, step, injectConflict } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/sim.js";
import { SEP } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/data/airspace.js";
import * as tact from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/tactical.js";
const REF = { lat: 48.8566, lng: 2.3522 };

console.log("=== P4 : a portee de pop-up IDENTIQUE, la cible tiree au hasard change le verdict ===");
const POP = 600;
const seen = new Map();
for (let k = 0; k < 40; k++) {
  Math.random = () => (k % 20) / 20 + 0.001;   // balaye les cibles possibles
  const flights = generateFleet(40, 42, 600);
  const { assignments } = deconflict(flights, REF);
  const sim = buildSim(assignments, REF);
  for (let t = 0; t < 200; t++) step(sim, 1, SEP);
  const inj = injectConflict(sim, { rangeM: POP, speed: 55 }, SEP);
  if (!inj) continue;
  const tgt = sim.agents[sim.agents.length - 1];
  const target = sim.encounters[sim.encounters.length - 1].target;
  for (let i = 0; i < 400 && !sim.stats.last; i++) step(sim, 1, SEP);
  if (!sim.stats.last) continue;
  const key = `${target.name} (v=${target.speed} m/s, fermeture ${target.speed + 55} m/s, t_CPA=${(POP/(target.speed+55)).toFixed(1)}s)`;
  if (!seen.has(key)) seen.set(key, sim.stats.last.outcome + " min=" + sim.stats.last.minSep + "m");
}
for (const [k, v] of seen) console.log("  " + k.padEnd(70) + " -> " + v);

console.log("\n=== P5 : la couche tactique sert-elle a quelque chose sans injection ? ===");
for (const n of [40, 100, 150]) {
  const flights = generateFleet(n, 42, 600);
  const { assignments } = deconflict(flights, REF);
  const sim = buildSim(assignments, REF);
  let conf = 0, los = 0, maxT = 0;
  for (let t = 0; t < 4000; t++) {
    const c = step(sim, 1, SEP);
    conf += c.length;
    for (let i = 0; i < sim.agents.length; i++)
      for (let j = i + 1; j < sim.agents.length; j++) {
        const A = sim.agents[i], B = sim.agents[j];
        if (!A.airborne || !B.airborne) continue;
        const p = tact.predictPair(A, B, SEP);
        if (p.los) los++;
      }
    if (sim.agents.every(a => a.done || !a.airborne) && t > 100) { maxT = t; break; }
  }
  console.log(`  N=${n} : conflits tactiques predits (cumul pas-a-pas) = ${conf}, evenements LoS = ${los}, duree = ${maxT}s`);
}
