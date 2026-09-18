import { deconflict } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/strategic.js";
import { generateFleet } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/fleet.js";
import { buildSim, step, injectConflict } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/sim.js";
import { SEP, TACT } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/data/airspace.js";
import { makeRng } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/geo.js";
const REF = { lat: 48.8566, lng: 2.3522 };
function run(popup) {
  const flights = generateFleet(40, 42, 600);
  const { assignments } = deconflict(flights, REF);
  const sim = buildSim(assignments, REF);
  for (let t = 0; t < 200; t++) step(sim, 1, SEP);
  const rng = makeRng(7);
  const inj = injectConflict(sim, { rangeM: popup, speed: 55, rng }, SEP);
  if (!inj) return null;
  for (let k = 0; k < 600 && !sim.stats.last; k++) step(sim, 1, SEP);
  return sim.stats.last ? { ...sim.stats.last } : null;
}
console.log("Enveloppe de recuperation apres correction (cible deterministe, graine 7)\n");
console.log("popup_m  fermeture  t_CPA   verdict          sep_min");
for (let p = 400; p <= 1000; p += 50) {
  const r = run(p);
  if (!r) continue;
  console.log(String(p).padEnd(9) + String(r.closure).padEnd(11) + r.tcpa.toFixed(1).padEnd(8)
    + (r.outcome === "resolved" ? "resolved" : "LOSS OF SEP").padEnd(17) + r.minSep + " m");
}
const need = SEP.los_horiz_m / TACT.lat_rate_ms + TACT.react_s;
console.log(`\nSeuil analytique de non-perte : t_CPA >= ${SEP.los_horiz_m}/${TACT.lat_rate_ms} + ${TACT.react_s} = ${need.toFixed(2)} s`);
const needWC = SEP.daa_hmd_m / TACT.lat_rate_ms + TACT.react_s;
console.log(`Seuil analytique de retablissement du well clear : ${SEP.daa_hmd_m}/${TACT.lat_rate_ms} + ${TACT.react_s} = ${needWC.toFixed(2)} s`);
