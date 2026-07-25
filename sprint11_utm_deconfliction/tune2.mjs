import { REF } from "./src/data/vertiports.js";
import { scalingSweep } from "./src/models/fleet.js";
const {rows,knee}=scalingSweep(REF,[10,20,30,40,50,60,80,100,120,150],42);
for(const r of rows) console.log(`N${String(r.n).padStart(3)}  conflicts=${String(r.baselineConflicts).padStart(3)}  meanDelay=${r.delayMean_min.toFixed(2)}min  residual=${String(r.residual).padStart(2)}  thru=${r.throughput_ph.toFixed(0)}/h`);
console.log("KNEE:", knee);
