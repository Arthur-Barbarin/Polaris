import { deconflict } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/strategic.js";
import { generateFleet } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/fleet.js";
const REF = { lat: 48.8566, lng: 2.3522 };

console.log("=== P1 : coherence intent vs delai declare (vols residuels) ===");
for (const n of [120, 150]) {
  const flights = generateFleet(n, 42, 600);
  const { assignments, metrics } = deconflict(flights, REF);
  const res = assignments.filter(a => !a.resolved);
  console.log(`\nN=${n} : residuels=${res.length}`);
  for (const a of res.slice(0, 4)) {
    const declared = a.flight.dep + a.delay_s;
    const flown = a.intent.dep;
    console.log(`  vol ${a.flight.id}: dep=${a.flight.dep.toFixed(1)}s delay_s=${a.delay_s}`
      + ` -> depart DECLARE ${declared.toFixed(1)}s, intent REELLEMENT vole a ${flown.toFixed(1)}s`
      + `  ecart=${(declared - flown).toFixed(0)}s`);
  }
  const phantom = res.length * 900;
  console.log(`  delai total declare = ${metrics.delayTotal_s}s dont ${phantom}s fantomes (${(100*phantom/metrics.delayTotal_s).toFixed(0)}%)`);
  console.log(`  delai moyen affiche = ${(metrics.delayMean_s/60).toFixed(2)} min`);
  console.log(`  delai moyen si on retire les fantomes = ${((metrics.delayTotal_s - phantom)/flights.length/60).toFixed(2)} min`);
}
