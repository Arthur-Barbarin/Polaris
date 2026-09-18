import { deconflict } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/strategic.js";
import { generateFleet } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/fleet.js";
const REF = { lat: 48.8566, lng: 2.3522 };
console.log("Comparaison de trois definitions de debit (graine 42)\n");
console.log("N    accept  rejet  span_arr  debit_arr  span_dep  debit_dep  pic_60min");
for (let n = 100; n <= 165; n += 5) {
  const flights = generateFleet(n, 42, 600);
  const { assignments } = deconflict(flights, REF);
  const acc = assignments.filter(a => a.accepted);
  const deps = acc.map(r => r.flight.dep + r.delay_s).sort((a,b)=>a-b);
  const arrs = acc.map(r => r.intent.arr);
  const spanArr = Math.max(1, Math.max(...arrs) - Math.min(...deps));
  const spanDep = Math.max(1, deps[deps.length-1] - deps[0]);
  // pic : plus grand nombre de departs acceptes dans une fenetre glissante d'une heure
  let peak = 0;
  for (let i = 0; i < deps.length; i++) {
    let j = i; while (j < deps.length && deps[j] - deps[i] <= 3600) j++;
    peak = Math.max(peak, j - i);
  }
  console.log(String(n).padEnd(5) + String(acc.length).padEnd(8) + String(n-acc.length).padEnd(7)
    + spanArr.toFixed(0).padEnd(10) + ((acc.length/spanArr)*3600).toFixed(0).padEnd(11)
    + spanDep.toFixed(0).padEnd(10) + ((acc.length/spanDep)*3600).toFixed(0).padEnd(11)
    + String(peak));
}
