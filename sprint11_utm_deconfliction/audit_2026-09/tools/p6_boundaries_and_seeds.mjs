import { deconflict } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/strategic.js";
import { generateFleet, scalingSweep } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/fleet.js";
import * as VP from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/data/vertiports.js";
const REF = { lat: 48.8566, lng: 2.3522 };

console.log("=== P6a : valeurs limites de la taille de flotte ===");
for (const n of [0, 1, 2, 5]) {
  try {
    const f = generateFleet(n, 42, 600);
    const { metrics } = deconflict(f, REF);
    console.log(`  N=${n} -> vols generes=${f.length} conflits=${metrics.baselineConflicts}`
      + ` delai_moy=${(metrics.delayMean_s/60).toFixed(2)}min debit=${metrics.throughput_ph.toFixed(1)}/h residuel=${metrics.residual}`);
  } catch (e) { console.log(`  N=${n} -> ERREUR: ${e.message}`); }
}

console.log("\n=== P6b : le genou de capacite depend-il de la graine ? ===");
const sizes = [10,20,40,80,100,120,150];
for (const seed of [1, 7, 42, 99, 1234]) {
  const { knee, rows } = scalingSweep(REF, sizes, seed);
  const r150 = rows[rows.length-1];
  console.log(`  graine ${String(seed).padEnd(5)} -> genou=${String(knee).padEnd(5)} conflits@150=${String(r150.baselineConflicts).padEnd(4)} residuel@150=${String(r150.residual).padEnd(4)} debit@150=${r150.throughput_ph.toFixed(0)}/h`);
}
