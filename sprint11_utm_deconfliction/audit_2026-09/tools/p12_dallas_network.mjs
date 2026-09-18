import { REGIONS } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/data/vertiports.js";
import { generateFleet, capacityBand } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/fleet.js";
import { deconflict } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/strategic.js";
import { haversine_m, toENU } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/geo.js";

const SIZES = [10,20,40,60,80,100,120,140,160];
for (const id of ["paris", "dallas"]) {
  const R = REGIONS[id];
  const vps = R.vertiports, ref = R.ref;
  console.log(`\n########## ${id.toUpperCase()}  (ref ${ref.lat}, ${ref.lng})`);

  // 1. geometrie du reseau
  let dmin = Infinity, dmax = 0, sum = 0, cnt = 0, rejected = 0;
  for (let i = 0; i < vps.length; i++)
    for (let j = i + 1; j < vps.length; j++) {
      const d = haversine_m(vps[i], vps[j]);
      dmin = Math.min(dmin, d); dmax = Math.max(dmax, d); sum += d; cnt++;
      if (d > 45000) rejected++;
    }
  console.log(`  paires ${cnt} | plus courte ${(dmin/1000).toFixed(1)} km | plus longue ${(dmax/1000).toFixed(1)} km | moyenne ${(sum/cnt/1000).toFixed(1)} km`);
  console.log(`  paires rejetees par le filtre 45 km : ${rejected}/${cnt} (${(100*rejected/cnt).toFixed(0)}%)`);

  // 2. distorsion de la projection equirectangulaire au point le plus eloigne
  let worst = 0, worstName = "";
  for (const v of vps) {
    const e = toENU(v, ref);
    const planar = Math.hypot(e.x, e.y);
    const geo = haversine_m(v, ref);
    const err = Math.abs(planar - geo) / geo;
    if (err > worst) { worst = err; worstName = v.id; }
  }
  console.log(`  distorsion equirectangulaire max : ${(worst*100).toFixed(3)} % (${worstName})  [MODEL.md annonce < 0.3 %]`);

  // 3. capacite
  const b = capacityBand(ref, SIZES, { nSeeds: 30, vertiports: vps });
  console.log(`  capacite : mediane ${b.knee_med?.toFixed(0)} ops, bande ${b.knee_p10?.toFixed(0)}-${b.knee_p90?.toFixed(0)} (${b.kneeSeedsReached}/30 graines atteignent le seuil)`);
  const last = b.band[b.band.length-1];
  console.log(`  a 160 demandees : acceptees ${last.accepted_p10.toFixed(0)}/${last.accepted_med.toFixed(0)}/${last.accepted_p90.toFixed(0)}, retard median ${last.delay_med.toFixed(2)} min`);

  // 4. la flotte generee est-elle saine ?
  const f = generateFleet(160, 42, 600, vps);
  const hops = f.map(x => haversine_m(x.origin, x.dest));
  console.log(`  flotte 160 : ${f.length} vols generes | trajet min ${(Math.min(...hops)/1000).toFixed(1)} km | max ${(Math.max(...hops)/1000).toFixed(1)} km`);
  const durs = f.map(x => haversine_m(x.origin, x.dest) / x.vehicle.cruise_ms / 60);
  console.log(`  duree de vol : min ${Math.min(...durs).toFixed(1)} min | max ${Math.max(...durs).toFixed(1)} min`);
}
