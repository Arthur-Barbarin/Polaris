import { useEffect, useMemo, useRef, useState } from "react";
import MapView from "./components/MapView.jsx";
import ScalingChart from "./components/ScalingChart.jsx";
import { REGIONS } from "./data/vertiports.js";
import { generateFleet, capacityBand } from "./models/fleet.js";
import { deconflict } from "./models/strategic.js";
import { buildSim, step, viewModel, injectConflict, SIM_DT } from "./models/sim.js";
import { toLatLng, makeRng } from "./models/geo.js";
import { SEP } from "./data/airspace.js";

const SWEEP_SIZES = [10, 20, 40, 60, 80, 100, 120, 140, 160];
const CAPACITY_SEEDS = 30;

export default function App() {
  const [regionId, setRegionId] = useState("paris");
  const [fleetSize, setFleetSize] = useState(40);
  const [seed, setSeed] = useState(42);
  const [running, setRunning] = useState(true);
  const [speedMult, setSpeedMult] = useState(6);
  const [popupRange, setPopupRange] = useState(1200);

  const region = REGIONS[regionId];
  const REF = region.ref;

  const [vehicles, setVehicles] = useState([]);
  const [conflictLines, setConflictLines] = useState([]);
  const [stats, setStats] = useState({ minSep: Infinity, encounters: 0, resolved: 0, los: 0, last: null });

  const simRef = useRef(null);

  // strategic plan (recomputed on fleet/seed change)
  const plan = useMemo(() => {
    const flights = generateFleet(fleetSize, seed, 600, region.vertiports);
    return deconflict(flights, REF);
  }, [fleetSize, seed, regionId]);

  // Capacity band: 30 independent demand draws, not one. A single draw put this
  // network's knee anywhere between 80 and 150 depending on the seed, so the
  // headline is now a median with a 10th-90th percentile band.
  const cap = useMemo(
    () => capacityBand(REF, SWEEP_SIZES, { nSeeds: CAPACITY_SEEDS, vertiports: region.vertiports }),
    [regionId]
  );

  // Seeded PRNG for intruder injection, so an encounter is reproducible from
  // the scenario seed rather than from Math.random.
  const injRng = useRef(makeRng(seed * 7919 + 13));
  useEffect(() => { injRng.current = makeRng(seed * 7919 + 13); }, [seed, regionId]);

  // (re)build the live sim whenever the plan changes
  useEffect(() => {
    simRef.current = buildSim(plan.assignments, REF);
    setVehicles(viewModel(simRef.current));
    setConflictLines([]);
    setStats({ ...simRef.current.stats });
  }, [plan]);

  // animation loop
  useEffect(() => {
    if (!running) return;
    const iv = setInterval(() => {
      const sim = simRef.current;
      if (!sim) return;
      const dt = 0.5 * speedMult;
      const conflicts = step(sim, dt, SEP);
      // autoloop when the whole schedule has flown
      if (sim.agents.every((a) => a.done || a.intruder)) {
        simRef.current = buildSim(plan.assignments, REF);
        return;
      }
      setVehicles(viewModel(sim));
      setConflictLines(
        conflicts.map((c) => ({
          a: toLatLng(sim.agents[c.i].pos, sim.ref),
          b: toLatLng(sim.agents[c.j].pos, sim.ref),
        }))
      );
      setStats({ ...sim.stats });
    }, 50);
    return () => clearInterval(iv);
  }, [running, speedMult, plan]);

  const airborne = vehicles.length;
  const minSep = stats.minSep === Infinity ? "—" : Math.round(stats.minSep);
  const m = plan.metrics;

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <div className="brand">POLARIS · Sprint 11</div>
          <h1>UTM Fleet Deconfliction Studio</h1>
          <div className="sub">{region.name} · strategic 4D intent + live tactical detect-and-avoid</div>
        </div>
        <div className="live-metrics">
          <Metric label="airborne" value={airborne} />
          <Metric label="min sep (m)" value={minSep} warn={stats.minSep < SEP.los_horiz_m} />
          <Metric label="intruders avoided" value={stats.resolved} accent />
          <Metric label="loss-of-sep" value={stats.los} warn={stats.los > 0} />
        </div>
      </header>

      <div className="body">
        <div className="mapcol">
          <MapView vehicles={vehicles} conflicts={conflictLines} assignments={plan.assignments}
                   vertiports={region.vertiports} center={region.center} zoom={region.zoom} />
          <div className="maplegend">
            <span><i className="tri" style={{ color: "#38bdf8" }}>▲</i> cooperative eVTOL</span>
            <span><i className="tri" style={{ color: "#ef4444" }}>▲</i> non-cooperative intruder</span>
            <span><i className="dash" /> predicted conflict (CPA)</span>
          </div>
        </div>

        <aside className="panel">
          <div className="controls">
            <div className="ctl">
              <label>Region</label>
              <div className="segmented">
                {Object.values(REGIONS).map((r) => (
                  <button key={r.id}
                          className={`seg ${regionId === r.id ? "on" : ""}`}
                          onClick={() => setRegionId(r.id)}>
                    {r.id === "paris" ? "Paris" : "Dallas–Fort Worth"}
                  </button>
                ))}
              </div>
            </div>
            <div className="ctl">
              <label>Fleet size — {fleetSize} operations in the demand window</label>
              <input type="range" min="5" max="150" step="5" value={fleetSize}
                     onChange={(e) => setFleetSize(+e.target.value)} />
            </div>
            <div className="ctl">
              <label>Sim speed — {speedMult}× <span className="fine">(display only; model integrated at {SIM_DT} s)</span></label>
              <input type="range" min="1" max="20" step="1" value={speedMult}
                     onChange={(e) => setSpeedMult(+e.target.value)} />
            </div>
            <div className="ctl">
              <label>Intruder pop-up range — {popupRange} m {popupRange <= 600 ? "(inside the recovery envelope — expect a loss of separation)" : popupRange >= 1600 ? "(early — easy)" : ""}</label>
              <input type="range" min="300" max="2200" step="100" value={popupRange}
                     onChange={(e) => setPopupRange(+e.target.value)} />
            </div>
            <div className="btnrow">
              <button className="btn" onClick={() => setRunning((r) => !r)}>
                {running ? "❚❚ Pause" : "▶ Play"}
              </button>
              <button className="btn danger"
                      onClick={() => simRef.current && injectConflict(simRef.current, { rangeM: popupRange, speed: 55, rng: injRng.current }, SEP)}>
                ⚠ Inject intruder
              </button>
              <button className="btn ghost" onClick={() => setSeed((s) => s + 1)}>↻ New scenario #{seed}</button>
            </div>
          </div>

          <div className="planbox">
            <h3>Tactical detect &amp; avoid · {stats.resolved} avoided / {stats.los} loss-of-sep</h3>
            {stats.last ? (
              <div className={`encounter ${stats.last.outcome === "resolved" ? "ok" : "bad"}`}>
                Last intruder: popped up at <b>{stats.last.range} m</b> on a{" "}
                <b>{stats.last.target}</b> → closure <b>{stats.last.closure} m/s</b> →{" "}
                <b>{stats.last.tcpa.toFixed(1)} s</b> to closest approach →{" "}
                <b>{stats.last.outcome}</b> (min sep {stats.last.minSep} m)
                <div className="fine" style={{ marginTop: 4 }}>
                  Range alone does not set the difficulty: closure runs from 80 m/s
                  (VoloCity) to 144 m/s (Joby S4), so the same pop-up range gives a
                  different time to closest approach. Time is what the envelope is made of.
                </div>
              </div>
            ) : (
              <p className="fine" style={{ marginTop: 2 }}>
                Click "Inject intruder" to spawn a non-cooperative aircraft on a head-on
                course. It's detected at the pop-up range you set. The give-way eVTOL takes
                ~{"2.5"} s to react, then opens separation at a bounded rate — so a late
                (short-range) pop-up can leave too little time, and separation is lost.
                That threshold is the safety envelope.
              </p>
            )}
          </div>

          <div className="planbox">
            <h3>Strategic plan for {m.n} ops</h3>
            <Row k="conflicts before deconfliction" v={m.baselineConflicts} />
            <Row k="resolved by altitude layering" v={m.layerChanges} />
            <Row k="mean departure delay (accepted)" v={`${(m.delayMean_s / 60).toFixed(1)} min`} />
            <Row k="accepted" v={`${m.accepted} / ${m.n} (${(m.acceptanceRate * 100).toFixed(0)}%)`} />
            <Row k="rejected (no slot within the delay cap)" v={m.rejected} warn={m.rejected > 0} />
            <Row k="accepted movements" v={`${m.throughput_ph.toFixed(0)} /h`} accent />
          </div>

          <div className="planbox">
            <h3>
              Capacity {cap.knee_med != null
                ? `≈ ${Math.round(cap.knee_med)} ops (band ${Math.round(cap.knee_p10)}–${Math.round(cap.knee_p90)})`
                : "· headroom across the whole sweep"}
            </h3>
            <ScalingChart band={cap.band} kneeMed={cap.knee_med} kneeP10={cap.knee_p10}
                          kneeP90={cap.knee_p90} serviceLevel={cap.serviceLevel} />
            <p className="fine">
              Strategic deconfliction absorbs conflicts into altitude layers and departure
              delays until the network can no longer serve the request. Measured over{" "}
              <b>{cap.nSeeds} independent demand draws</b>: capacity is a property of the
              network <i>and</i> of the demand profile, and a single draw moves this
              network's answer by roughly ±10%. The number to put in front of an operator
              is the band, not the point.
            </p>
          </div>

          <p className="honesty">
            <b>Honesty note.</b> Synthetic traffic; no real flights or surveillance.
            Separation thresholds ({SEP.strat_horiz_m} m strategic / {SEP.daa_hmd_m} m DAA)
            are illustrative UAM values, editable in <code>data/airspace.js</code>, not
            regulatory minima. Every displayed number is reproduced by <code>node verify.mjs</code>.
          </p>
        </aside>
      </div>
    </div>
  );
}

function Metric({ label, value, accent, warn }) {
  return (
    <div className={`bigmetric ${accent ? "accent" : ""} ${warn ? "warn" : ""}`}>
      <div className="bm-val">{value}</div>
      <div className="bm-lab">{label}</div>
    </div>
  );
}
function Row({ k, v, accent, warn }) {
  return (
    <div className="prow">
      <span>{k}</span>
      <span className={`pval ${accent ? "accent" : ""} ${warn ? "warn" : ""}`}>{v}</span>
    </div>
  );
}
