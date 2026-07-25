// Numerical verification. Run with: `node verify.mjs`
// Written to be audited by a UTM / UAM engineer: every number the UI shows can
// be reconstructed here. Deterministic (seeded RNG), so results are stable.

import { REF } from "./src/data/vertiports.js";
import { SEP, ALT_LAYERS } from "./src/data/airspace.js";
import { cpaHoriz, tauMod, haversine_m, toENU } from "./src/models/geo.js";
import { predictPair, resolve } from "./src/models/tactical.js";
import { generateFleet, scalingSweep } from "./src/models/fleet.js";
import { deconflict, minSep, buildIntent } from "./src/models/strategic.js";
import { buildSim, step, injectConflict } from "./src/models/sim.js";

const fmt = (x, n = 1) => (x == null ? "—" : Number(x).toFixed(n));
const line = (l, v) => console.log(l.padEnd(46), v);
let fails = 0;
const check = (name, cond, got) => {
  console.log(`${cond ? "✓" : "✗"} ${name}`.padEnd(52), got ?? "");
  if (!cond) fails++;
};

console.log("\n=== 1. CPA geometry (analytic sanity) ===");
// Two vehicles closing head-on: 2000 m apart, 50 m/s each toward the other.
{
  const p1 = { x: -1000, y: 0 }, v1 = { x: 50, y: 0 };
  const p2 = { x: 1000, y: 0 }, v2 = { x: -50, y: 0 };
  const c = cpaHoriz(p1, v1, p2, v2);
  check("head-on t_cpa = 20 s", Math.abs(c.t_cpa - 20) < 1e-6, `${fmt(c.t_cpa, 2)} s`);
  check("head-on HMD = 0 m", c.hmd < 1e-6, `${fmt(c.hmd, 2)} m`);
}
// Parallel offset tracks never converge: HMD = current offset, closing=false.
{
  const c = cpaHoriz({ x: 0, y: 200 }, { x: 40, y: 0 }, { x: 0, y: 0 }, { x: 40, y: 0 });
  check("parallel HMD = 200 m", Math.abs(c.hmd - 200) < 1e-6, `${fmt(c.hmd, 1)} m`);
  check("parallel not closing", c.closing === false, String(c.closing));
}
// Crossing 90°: (-1500,0)@(30,0) and (0,-1500)@(0,30) meet at origin at t=50.
{
  const c = cpaHoriz({ x: -1500, y: 0 }, { x: 30, y: 0 }, { x: 0, y: -1500 }, { x: 0, y: 30 });
  check("crossing t_cpa = 50 s", Math.abs(c.t_cpa - 50) < 1e-6, `${fmt(c.t_cpa, 1)} s`);
  check("crossing HMD ~ 0 m", c.hmd < 1e-6, `${fmt(c.hmd, 3)} m`);
}

console.log("\n=== 2. Modified tau (DO-365 form) ===");
{
  // closing head-on, DMOD = 150 m, range 2000, rdot = -100 m/s
  const tau = tauMod({ x: -1000, y: 0 }, { x: 50, y: 0 }, { x: 1000, y: 0 }, { x: -50, y: 0 }, 150);
  // tau_mod = (150^2 - 2000^2)/(2000 * -100) = ( -3977500 )/(-200000)=19.8875
  check("tau_mod ≈ 19.89 s", Math.abs(tau - 19.8875) < 1e-3, `${fmt(tau, 3)} s`);
  const tauOpen = tauMod({ x: 0, y: 0 }, { x: 50, y: 0 }, { x: -1000, y: 0 }, { x: 0, y: 0 }, 150);
  check("tau = +Inf when opening", tauOpen === Infinity, String(tauOpen));
}

console.log("\n=== 3. Well-clear prediction + resolution ===");
{
  const A = { pos: { x: -800, y: 0 }, vel: { x: 55, y: 0 }, alt: 360, priority: 0, airborne: true };
  const B = { pos: { x: 800, y: 0 }, vel: { x: -55, y: 0 }, alt: 360, priority: 5, airborne: true, speed: 55 };
  const p = predictPair(A, B, SEP);
  check("head-on same layer => violation", p.wellClearViolation === true, `HMD=${fmt(p.hmd)} vert=${fmt(p.vert)}`);
  const adv = resolve(B, A, SEP); // B is give-way (higher priority value)
  check("resolution advisory found", adv.ok === true, `type=${adv.type}`);
  // vertical-separated pair: no violation
  const B2 = { ...B, alt: 360 + SEP.daa_vert_m + 5 };
  check("layer-separated => no violation", predictPair(A, B2, SEP).wellClearViolation === false,
        `vert=${fmt(Math.abs(A.alt - B2.alt))} m`);
}

console.log("\n=== 3b. Tactical envelope: late pop-up => loss of separation ===");
{
  const runAt = (range) => {
    const flights = generateFleet(60, 7, 600);
    const { assignments } = deconflict(flights, REF);
    const sim = buildSim(assignments, REF);
    for (let k = 0; k < 200 && sim.agents.filter((a) => a.airborne).length < 6; k++) step(sim, 1.0);
    if (!injectConflict(sim, { rangeM: range, speed: 55 })) return null;
    for (let k = 0; k < 400 && sim.stats.encounters === 0; k++) step(sim, 0.25);
    return sim.stats.last;
  };
  const near = runAt(300), mid = runAt(700), far = runAt(1400);
  line("pop-up 300 m:", `${near.tcpa.toFixed(1)} s → ${near.outcome} (min ${near.minSep} m)`);
  line("pop-up 700 m:", `${mid.tcpa.toFixed(1)} s → ${mid.outcome} (min ${mid.minSep} m)`);
  line("pop-up 1400 m:", `${far.tcpa.toFixed(1)} s → ${far.outcome} (min ${far.minSep} m)`);
  check("late pop-up (300 m) => loss of sep", near.outcome === "LOSS OF SEP", `min ${near.minSep} m`);
  check("early pop-up (1400 m) => resolved", far.outcome === "resolved", `min ${far.minSep} m`);
  check("envelope is monotone (near ≤ far min sep)", near.minSep <= far.minSep, `${near.minSep} ≤ ${far.minSep}`);
}

console.log("\n=== 4. Strategic intent + minSep ===");
{
  // Two flights head-on along the same corridor => they pass through, minSep ~ 0.
  const fA = { origin: { lat: 48.80, lng: 2.35, id: "a1" }, dest: { lat: 48.92, lng: 2.35, id: "a2" },
               vehicle: { cruise_ms: 50 }, dep: 0 };
  const fB = { origin: { lat: 48.92, lng: 2.35, id: "b1" }, dest: { lat: 48.80, lng: 2.35, id: "b2" },
               vehicle: { cruise_ms: 50 }, dep: 0 };
  const iA = buildIntent(fA, REF), iB = buildIntent(fB, REF);
  const ms = minSep(iA, iB);
  line("head-on corridor min horizontal sep:", `${fmt(ms, 0)} m (buffer ${SEP.strat_horiz_m} m)`);
  check("head-on intents converge (minSep < buffer)", isFinite(ms) && ms < SEP.strat_horiz_m, `${fmt(ms, 1)} m`);
  // Non-overlapping departures => no interaction => Infinity.
  const iC = buildIntent({ ...fB, dep: 100000 }, REF);
  check("non-overlapping windows => minSep = Inf", minSep(iA, iC) === Infinity, "Infinity");
  check("layers spaced by strat_vert_m", ALT_LAYERS[1] - ALT_LAYERS[0] === SEP.strat_vert_m,
        `${ALT_LAYERS[1] - ALT_LAYERS[0]} m`);
}

console.log("\n=== 5. Deconfliction reduces conflicts (fleet = 40, seed 42) ===");
{
  const flights = generateFleet(40, 42);
  const { assignments, metrics } = deconflict(flights, REF);
  line("baseline conflicts:", metrics.baselineConflicts);
  line("mean departure delay:", `${fmt(metrics.delayMean_s / 60, 2)} min`);
  line("layer changes used:", metrics.layerChanges);
  line("unresolved (residual):", metrics.residual);
  line("throughput:", `${fmt(metrics.throughput_ph, 0)} ops/h`);
  // Post-plan, count residual same-layer conflicts directly from assignments.
  let post = 0;
  for (let i = 0; i < assignments.length; i++)
    for (let j = i + 1; j < assignments.length; j++)
      if (assignments[i].layer === assignments[j].layer &&
          minSep(assignments[i].intent, assignments[j].intent) < SEP.strat_horiz_m) post++;
  check("plan clears baseline conflicts", post <= metrics.residual,
        `post-plan same-layer conflicts = ${post}`);
  check("residual == flights flagged unresolved",
        metrics.residual === assignments.filter((a) => !a.resolved).length, String(metrics.residual));
}

console.log("\n=== 6. Capacity scaling sweep (seed 42) — the headline chart ===");
{
  const { rows, knee } = scalingSweep(REF, [10, 20, 40, 80, 120, 150], 42);
  for (const r of rows)
    line(`  N=${String(r.n).padStart(3)}`,
      `conflicts=${String(r.baselineConflicts).padStart(4)}  meanDelay=${fmt(r.delayMean_min, 2)} min  residual=${r.residual}  thru=${fmt(r.throughput_ph, 0)}/h`);
  const mono = rows.every((r, i) => i === 0 || r.baselineConflicts >= rows[i - 1].baselineConflicts);
  check("conflicts grow monotonically with fleet", mono, "");
  line("capacity knee:", knee ? `${knee} ops` : "none within 150 (headroom)");
}

console.log("\n=== 7. Determinism (same seed => same numbers) ===");
{
  const a = deconflict(generateFleet(50, 99), REF).metrics;
  const b = deconflict(generateFleet(50, 99), REF).metrics;
  check("repeat run is byte-identical",
        a.baselineConflicts === b.baselineConflicts && a.delayTotal_s === b.delayTotal_s,
        `conflicts=${a.baselineConflicts}, delayTotal=${a.delayTotal_s}s`);
}

console.log("\n=== 8. Network geometry spot checks (Paris) ===");
{
  const d = haversine_m({ lat: 48.8420, lng: 2.3660 }, { lat: 48.8920, lng: 2.2380 }); // Austerlitz -> La Défense
  line("Austerlitz → La Défense:", `${fmt(d / 1000, 1)} km`);
  check("distance in plausible urban range", d > 8000 && d < 14000, `${fmt(d / 1000, 2)} km`);
  const enu = toENU({ lat: 48.8920, lng: 2.2380 }, REF);
  line("La Défense ENU from Paris centre:", `(${fmt(enu.x, 0)}, ${fmt(enu.y, 0)}) m`);
}

console.log(`\n${fails === 0 ? "ALL CHECKS PASSED ✓" : `${fails} CHECK(S) FAILED ✗`}`);
process.exit(fails === 0 ? 0 : 1);
