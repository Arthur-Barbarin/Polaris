import { deconflict } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/strategic.js";
import { generateFleet } from "file:///sessions/rcw-01eo6ab9vey8mfrmbfh3prcf/mnt/Polaris_sprint/sprint11_utm_deconfliction/src/models/fleet.js";
const REF = { lat: 48.8566, lng: 2.3522 };
console.log("N    conf  delai_moy  resid  debit_ph   span_s   min(dep)  max(arr)  resolus  debit_resolus");
let prev = null, breaks = [];
for (let n = 90; n <= 160; n += 5) {
  const flights = generateFleet(n, 42, 600);
  const { assignments, metrics } = deconflict(flights, REF);
  const deps = assignments.map(r => r.flight.dep + r.delay_s);
  const arrs = assignments.map(r => r.intent.arr);
  const span = Math.max(1, Math.max(...arrs) - Math.min(...deps));
  const ok = assignments.filter(a => a.resolved).length;
  const thruOk = (ok / span) * 3600;
  console.log(
    String(n).padEnd(5) + String(metrics.baselineConflicts).padEnd(6)
    + (metrics.delayMean_s/60).toFixed(2).padEnd(11) + String(metrics.residual).padEnd(7)
    + metrics.throughput_ph.toFixed(0).padEnd(11) + span.toFixed(0).padEnd(9)
    + Math.min(...deps).toFixed(0).padEnd(10) + Math.max(...arrs).toFixed(0).padEnd(10)
    + String(ok).padEnd(9) + thruOk.toFixed(0));
  if (prev && metrics.throughput_ph < prev.t) breaks.push(`debit BAISSE de ${prev.t.toFixed(0)} a ${metrics.throughput_ph.toFixed(0)} entre N=${prev.n} et ${n}`);
  prev = { n, t: metrics.throughput_ph };
}
console.log("\nnon-monotonies de debit:", breaks.length ? breaks : "aucune (le debit ne fait que MONTER, y compris quand le reseau sature)");
