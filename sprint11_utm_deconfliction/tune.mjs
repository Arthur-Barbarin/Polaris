import { REF } from "./src/data/vertiports.js";
import { SEP } from "./src/data/airspace.js";
import { generateFleet } from "./src/models/fleet.js";
import { deconflict } from "./src/models/strategic.js";
const sizes=[20,50,80,120,150];
for (const win of [300, 480, 600, 900]) {
  for (const buf of [150, 300, 500]) {
    SEP.strat_horiz_m = buf;
    const out = sizes.map(n=>{
      const f = generateFleet(n,42,win);
      const m = deconflict(f,REF).metrics;
      return `N${n}:c${m.baselineConflicts}/d${(m.delayMean_s/60).toFixed(1)}/r${m.residual}`;
    }).join("  ");
    console.log(`win=${String(win).padStart(3)} buf=${String(buf).padStart(3)}`, out);
  }
}
