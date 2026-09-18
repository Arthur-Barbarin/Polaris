import { deconflict } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/strategic.js";
import { generateFleet, capacityBand } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/fleet.js";
const REF = { lat: 48.8566, lng: 2.3522 };
const SIZES = [10,20,40,60,80,100,120,140,160];
// Impact d'un espacement de couches decouple du seuil DAA vertical.
// On simule l'effet en changeant le nombre de couches disponibles : l'espacement
// n'entre pas dans la deconfliction strategique (seule compte l'appartenance a
// une couche), donc la capacite ne change PAS avec l'espacement. Verifions-le.
const b = capacityBand(REF, SIZES, { nSeeds: 30 });
console.log(`capacite actuelle : mediane ${b.knee_med?.toFixed(0)}, bande ${b.knee_p10?.toFixed(0)}-${b.knee_p90?.toFixed(0)}`);
console.log("\nLa deconfliction strategique ne compare que l'identite de la couche (a.layer !== b.layer),");
console.log("pas la distance verticale. Changer l'espacement 30 -> 45 m ne touche donc AUCUN chiffre de capacite.");
console.log("Cela ne change que le seuil tactique vertical et la marge reelle entre couches.\n");
// combien de paires se croisent a moins de 60 m horizontal sur des couches adjacentes ?
import { buildSim, step } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/sim.js";
import { SEP } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/data/airspace.js";
import { sub, norm } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/geo.js";
for (const n of [40, 100, 150]) {
  const { assignments } = deconflict(generateFleet(n, 42, 600), REF);
  const sim = buildSim(assignments, REF);
  let over = 0, seen = new Set();
  for (let t = 0; t < 3500; t++) {
    step(sim, 1, SEP);
    for (let i = 0; i < sim.agents.length; i++)
      for (let j = i + 1; j < sim.agents.length; j++) {
        const A = sim.agents[i], B = sim.agents[j];
        if (!A.airborne || !B.airborne) continue;
        const h = norm(sub(A.pos, B.pos));
        if (h < SEP.los_horiz_m) { const k = `${A.id}-${B.id}`; if (!seen.has(k)) { seen.add(k); over++; } }
      }
    if (sim.agents.every(a => a.done || !a.airborne) && t > 100) break;
  }
  console.log(`N=${n} : ${over} paires distinctes se croisent a moins de ${SEP.los_horiz_m} m horizontalement, separees uniquement par les ${SEP.strat_vert_m} m de couche`);
}
