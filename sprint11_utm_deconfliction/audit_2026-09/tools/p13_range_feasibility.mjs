import { REGIONS } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/data/vertiports.js";
import { generateFleet } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/fleet.js";
import { haversine_m } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/geo.js";
// Portees publiees (memes sources que le Sprint 5 quand elles existent)
const RANGE_KM = { jobys4: 240, midnight: 97, wisk6: 145, vx4: 160, volocity: 35 };
console.log("Faisabilite de portee par vehicule — le generateur filtre a 45 km GLOBAL,");
console.log("et tire le vehicule APRES avoir accepte le trajet.\n");
for (const id of ["paris", "dallas"]) {
  const R = REGIONS[id];
  const f = generateFleet(400, 42, 600, R.vertiports);
  const byV = {};
  for (const x of f) {
    const d = haversine_m(x.origin, x.dest) / 1000;
    const k = x.vehicle.id;
    byV[k] ||= { n: 0, bad: 0, worst: 0 };
    byV[k].n++;
    if (d > RANGE_KM[k]) { byV[k].bad++; byV[k].worst = Math.max(byV[k].worst, d); }
  }
  console.log(`### ${id} (400 vols)`);
  for (const [k, v] of Object.entries(byV))
    console.log(`  ${k.padEnd(10)} portee ${String(RANGE_KM[k]).padStart(3)} km | ${v.n} vols | ${v.bad} infaisables (${(100*v.bad/v.n).toFixed(0)}%)`
      + (v.bad ? ` | pire trajet ${v.worst.toFixed(1)} km` : ""));
  const tot = Object.values(byV).reduce((a,b)=>a+b.n,0), bad = Object.values(byV).reduce((a,b)=>a+b.bad,0);
  console.log(`  TOTAL ${bad}/${tot} vols infaisables (${(100*bad/tot).toFixed(1)}%)\n`);
}
