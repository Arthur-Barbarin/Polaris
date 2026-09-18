import { capacityBand, scalingSweep } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/fleet.js";
const REF = { lat: 48.8566, lng: 2.3522 };
const SIZES = [10,20,40,60,80,100,120,140,160];
const t0 = Date.now();
const b = capacityBand(REF, SIZES, { nSeeds: 30 });
console.log(`bande sur ${b.nSeeds} graines, niveau de service ${(b.serviceLevel*100).toFixed(0)}%  (${((Date.now()-t0)/1000).toFixed(1)} s)`);
console.log(`\ngenou : mediane ${b.knee_med?.toFixed(0)} ops, bande ${b.knee_p10?.toFixed(0)} a ${b.knee_p90?.toFixed(0)}  (${b.kneeSeedsReached}/${b.nSeeds} graines atteignent le seuil)`);
console.log("\nN     acceptees p10/med/p90     retard_moy_min p10/med/p90");
for (const r of b.band)
  console.log(String(r.n).padEnd(6)
    + `${r.accepted_p10.toFixed(0)} / ${r.accepted_med.toFixed(0)} / ${r.accepted_p90.toFixed(0)}`.padEnd(24)
    + `${r.delay_p10.toFixed(2)} / ${r.delay_med.toFixed(2)} / ${r.delay_p90.toFixed(2)}`);
