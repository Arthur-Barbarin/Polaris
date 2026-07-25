import { useEffect, useMemo, useRef, useState } from "react";
import MapView from "./components/MapView.jsx";
import ScalingChart from "./components/ScalingChart.jsx";
import { REF } from "./data/vertiports.js";
import { generateFleet, scalingSweep } from "./models/fleet.js";
import { deconflict } from "./models/strategic.js";
import { buildSim, step, viewModel, injectConflict } from "./models/sim.js";
import { toLatLng } from "./models/geo.js";
import { SEP } from "./data/airspace.js";

const SWEEP_SIZES = [10, 20, 30, 40, 50, 60, 80, 100, 120, 150];

export default function App() {
  const [fleetSize, setFleetSize] = useState(40);
  const [seed, setSeed] = useState(42);
  const [running, setRunning] = useState(true);
  const [speedMult, setSpeedMult] = useState(6);

  const [vehicles, setVehicles] = useState([]);
  const [conflictLines, setConflictLines] = useState([]);
  const [stats, setStats] = useState({ losEvents: 0, conflictsResolved: 0, minSep: Infinity, maneuvers: 0 });

  const simRef = useRef(null);

  // strategic plan (recomputed on fleet/seed change)
  const plan = useMemo(() => {
    const flights = generateFleet(fleetSize, seed);
    return deconflict(flights, REF);
  }, [fleetSize, seed]);

  // capacity sweep (fixed sizes; cheap enough to recompute on seed change)
  const sweep = useMemo(() => scalingSweep(REF, SWEEP_SIZES, seed), [seed]);

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
          <div className="sub">Paris eVTOL corridor network · strategic 4D intent + live tactical detect-and-avoid</div>
        </div>
        <div className="live-metrics">
          <Metric label="airborne" value={airborne} />
          <Metric label="min sep (m)" value={minSep} warn={stats.minSep < SEP.los_horiz_m} />
          <Metric label="conflicts resolved" value={stats.conflictsResolved} accent />
          <Metric label="loss-of-sep" value={stats.losEvents} warn={stats.losEvents > 0} />
        </div>
      </header>

      <div className="body">
        <div className="mapcol">
          <MapView vehicles={vehicles} conflicts={conflictLines} assignments={plan.assignments} />
          <div className="maplegend">
            <span><i className="tri" style={{ color: "#38bdf8" }}>▲</i> cooperative eVTOL</span>
            <span><i className="tri" style={{ color: "#ef4444" }}>▲</i> non-cooperative intruder</span>
            <span><i className="dash" /> predicted conflict (CPA)</span>
          </div>
        </div>

        <aside className="panel">
          <div className="controls">
            <div className="ctl">
              <label>Fleet size — {fleetSize} simultaneous operations</label>
              <input type="range" min="5" max="150" step="5" value={fleetSize}
                     onChange={(e) => setFleetSize(+e.target.value)} />
            </div>
            <div className="ctl">
              <label>Sim speed — {speedMult}×</label>
              <input type="range" min="1" max="20" step="1" value={speedMult}
                     onChange={(e) => setSpeedMult(+e.target.value)} />
            </div>
            <div className="btnrow">
              <button className="btn" onClick={() => setRunning((r) => !r)}>
                {running ? "❚❚ Pause" : "▶ Play"}
              </button>
              <button className="btn danger" onClick={() => simRef.current && injectConflict(simRef.current, SEP)}>
                ⚠ Inject conflict
              </button>
              <button className="btn ghost" onClick={() => setSeed((s) => s + 1)}>↻ Reseed</button>
            </div>
          </div>

          <div className="planbox">
            <h3>Strategic plan for {m.n} ops</h3>
            <Row k="conflicts before deconfliction" v={m.baselineConflicts} />
            <Row k="resolved by altitude layering" v={m.layerChanges} />
            <Row k="mean departure delay" v={`${(m.delayMean_s / 60).toFixed(1)} min`} />
            <Row k="unresolved (over delay cap)" v={m.residual} warn={m.residual > 0} />
            <Row k="network throughput" v={`${m.throughput_ph.toFixed(0)} ops/h`} accent />
          </div>

          <div className="planbox">
            <h3>Capacity scaling {sweep.knee ? `· knee ≈ ${sweep.knee} ops` : "· headroom to 150"}</h3>
            <ScalingChart rows={sweep.rows} knee={sweep.knee} />
            <p className="fine">
              Conflicts grow ~quadratically with fleet size; strategic deconfliction
              absorbs them into altitude layers and small departure delays until the
              airspace saturates. That knee is the number to put in front of an operator.
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
