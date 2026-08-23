import { useEffect, useMemo, useRef, useState } from "react";
import MapView from "./components/MapView.jsx";
import { SweepChart, LatBandChart } from "./components/Charts.jsx";
import { PRESETS, PRESET_LIST, SITES } from "./data/presets.js";
import { buildWalker } from "./models/walker.js";
import {
  period, aFromAlt, footprintHalfAngle, footprintRadiusKm, sunSyncInclination,
} from "./models/orbit.js";
import {
  propagate, instantCoverage, coverageByLatBand, satsInView, siteRevisit, coverageSweep,
} from "./models/coverage.js";

const FOOTPRINT_LIMIT = 220; // above this we draw dots only (rendering cost)

export default function App() {
  const [presetId, setPresetId] = useState("iridium");
  const [cfg, setCfg] = useState({ ...PRESETS.iridium });
  const [siteId, setSiteId] = useState("paris");
  const [playing, setPlaying] = useState(true);
  const [rate, setRate] = useState(30); // sim-seconds per tick
  const [t, setT] = useState(0);

  const site = SITES.find((s) => s.id === siteId);
  const sats = useMemo(() => buildWalker(cfg), [cfg]);
  const half = useMemo(() => footprintHalfAngle(cfg.alt_km, cfg.minElev_deg), [cfg]);
  const total = sats.length;

  // live propagation
  const [subPoints, setSubPoints] = useState([]);
  const [coverage, setCoverage] = useState(0);
  const frame = useRef(0);

  useEffect(() => {
    const sp = propagate(sats, t);
    setSubPoints(sp);
    frame.current++;
    if (frame.current % 3 === 0 || coverage === 0)
      setCoverage(instantCoverage(sp, half, 6) * 100);
  }, [sats, half, t]);

  useEffect(() => {
    if (!playing) return;
    const iv = setInterval(() => setT((x) => x + rate), 60);
    return () => clearInterval(iv);
  }, [playing, rate]);

  // expensive analyses — only on config/site change
  const revisit = useMemo(
    () => siteRevisit(sats, site, half, 86400, 30),
    [sats, site, half]
  );
  const bands = useMemo(() => coverageByLatBand(propagate(sats, 0), half, 5), [sats, half]);

  const sweep = useMemo(() => {
    const planeCounts = [1, 2, 3, 4, 6, 8, 12, 18, 24].filter(
      (p) => p * cfg.satsPerPlane <= 900
    );
    const rows = coverageSweep(
      (planes, spp) =>
        buildWalker({ ...cfg, planes, satsPerPlane: spp }),
      planeCounts.map((p) => ({ planes: p, satsPerPlane: cfg.satsPerPlane })),
      cfg.alt_km, cfg.minElev_deg, 3, period(aFromAlt(cfg.alt_km))
    );
    const knee = rows.find((r) => r.coverage >= 99.0)?.n ?? null;
    return { rows, knee };
  }, [cfg.alt_km, cfg.inc_deg, cfg.minElev_deg, cfg.satsPerPlane, cfg.pattern, cfg.phasing]);

  const applyPreset = (id) => { setPresetId(id); setCfg({ ...PRESETS[id] }); setT(0); };
  const set = (k, v) => { setCfg((c) => ({ ...c, [k]: v })); setPresetId("custom"); };

  const inView = subPoints.length ? satsInView(subPoints, site, half) : 0;
  const per_min = period(aFromAlt(cfg.alt_km)) / 60;
  const fpRadius = footprintRadiusKm(cfg.alt_km, cfg.minElev_deg);
  const sso = sunSyncInclination(cfg.alt_km);
  const gap = revisit.maxGap_s;

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <div className="brand">POLARIS · Sprint 15</div>
          <h1>Constellation Coverage Studio</h1>
          <div className="sub">
            {presetId === "custom" ? "Custom shell" : PRESETS[presetId].name} · Walker{" "}
            {cfg.pattern === "star" ? "Star" : "Delta"} {total}/{cfg.planes}/{cfg.phasing} ·
            orbital period {per_min.toFixed(1)} min
          </div>
        </div>
        <div className="live-metrics">
          <Metric label="satellites" value={total} />
          <Metric label="global coverage" value={`${coverage.toFixed(1)}%`} accent />
          <Metric label={`in view · ${site.name}`} value={inView} warn={inView === 0} />
          <Metric
            label="max gap (24 h)"
            value={gap === 0 ? "none" : gap >= 3600 ? `${(gap / 3600).toFixed(1)} h` : `${Math.round(gap / 60)} min`}
            accent={gap === 0}
            warn={gap > 0}
          />
        </div>
      </header>

      <div className="body">
        <div className="mapcol">
          <MapView
            subPoints={subPoints}
            halfAngle={half}
            site={site}
            showFootprints={total <= FOOTPRINT_LIMIT}
            color="#38bdf8"
          />
          <div className="maplegend">
            <span><i className="sat" /> satellite sub-point</span>
            <span><i className="fp" /> visibility footprint (≥ {cfg.minElev_deg}° elevation)</span>
            <span><i className="site" /> {site.name}</span>
            {total > FOOTPRINT_LIMIT && <span className="muted">footprints hidden above {FOOTPRINT_LIMIT} sats</span>}
          </div>
        </div>

        <aside className="panel">
          <div className="ctl">
            <label>Constellation</label>
            <select value={presetId} onChange={(e) => applyPreset(e.target.value)}>
              {PRESET_LIST.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              {presetId === "custom" && <option value="custom">Custom</option>}
            </select>
            {presetId !== "custom" && <p className="fine">{PRESETS[presetId].note}</p>}
          </div>

          <div className="ctl">
            <label>Altitude — {cfg.alt_km} km <span className="hint">(period {per_min.toFixed(1)} min · footprint r ≈ {fpRadius.toFixed(0)} km)</span></label>
            <input type="range" min="300" max="25000" step="10" value={cfg.alt_km}
                   onChange={(e) => set("alt_km", +e.target.value)} />
          </div>
          <div className="ctl">
            <label>Inclination — {cfg.inc_deg}° {sso && <span className="hint">(sun-sync here = {sso.toFixed(1)}°)</span>}</label>
            <input type="range" min="0" max="100" step="0.1" value={cfg.inc_deg}
                   onChange={(e) => set("inc_deg", +e.target.value)} />
          </div>
          <div className="ctl2">
            <div>
              <label>Planes — {cfg.planes}</label>
              <input type="range" min="1" max="36" step="1" value={cfg.planes}
                     onChange={(e) => set("planes", +e.target.value)} />
            </div>
            <div>
              <label>Sats / plane — {cfg.satsPerPlane}</label>
              <input type="range" min="1" max="30" step="1" value={cfg.satsPerPlane}
                     onChange={(e) => set("satsPerPlane", +e.target.value)} />
            </div>
          </div>
          <div className="ctl">
            <label>Min elevation angle — {cfg.minElev_deg}°</label>
            <input type="range" min="0" max="40" step="1" value={cfg.minElev_deg}
                   onChange={(e) => set("minElev_deg", +e.target.value)} />
          </div>
          <div className="ctl2">
            <div>
              <label>Pattern</label>
              <div className="segmented">
                {["delta", "star"].map((p) => (
                  <button key={p} className={`seg ${cfg.pattern === p ? "on" : ""}`}
                          onClick={() => set("pattern", p)}>
                    {p === "delta" ? "Delta" : "Star"}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label>Ground site</label>
              <select value={siteId} onChange={(e) => setSiteId(e.target.value)}>
                {SITES.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          </div>
          <div className="btnrow">
            <button className="btn" onClick={() => setPlaying((p) => !p)}>
              {playing ? "❚❚ Pause" : "▶ Play"}
            </button>
            <button className="btn ghost" onClick={() => setT(0)}>↻ Reset t</button>
            <span className="tclock">t + {(t / 60).toFixed(0)} min</span>
          </div>

          <div className="planbox">
            <h3>Coverage of {site.name} over 24 h</h3>
            <Row k="time at least one sat in view" v={`${(revisit.coverageFrac * 100).toFixed(1)}%`}
                 accent={revisit.continuous} />
            <Row k="longest gap" v={gap === 0 ? "continuous — no gap" : gap >= 3600 ? `${(gap / 3600).toFixed(2)} h` : `${Math.round(gap / 60)} min`}
                 warn={gap > 0} accent={gap === 0} />
            <Row k="mean gap between passes" v={revisit.meanGap_s ? `${Math.round(revisit.meanGap_s / 60)} min` : "—"} />
            <Row k="passes per day" v={revisit.passes} />
            <Row k="peak sats in view" v={revisit.maxInView} />
          </div>

          <div className="planbox">
            <h3>How many satellites for global coverage?</h3>
            <SweepChart rows={sweep.rows} knee={sweep.knee} />
            <p className="fine">
              Coverage vs constellation size at {cfg.alt_km} km / {cfg.minElev_deg}° elevation,
              holding {cfg.satsPerPlane} sats per plane.{" "}
              {sweep.knee
                ? <>Continuous global coverage arrives at ≈ <b>{sweep.knee} satellites</b>.</>
                : <>No size in this sweep reaches continuous coverage — raise the altitude or lower the elevation mask.</>}{" "}
              Raise the altitude and this number collapses: footprint radius grows, so fewer
              satellites blanket the same Earth. That trade — satellites vs altitude vs launch
              cost vs link budget — is the whole constellation-design argument.
            </p>
          </div>

          <div className="planbox">
            <h3>Coverage by latitude</h3>
            <LatBandChart bands={bands} />
            <p className="fine">
              A {cfg.inc_deg.toFixed(1)}° shell cannot see much above ~{Math.min(90, cfg.inc_deg + (footprintHalfAngle(cfg.alt_km, cfg.minElev_deg) * 180) / Math.PI).toFixed(0)}°
              latitude. Drag inclination toward 90° and watch the polar ends fill in — this is why
              Iridium and OneWeb fly near-polar and Starlink's 53° shell does not serve the poles.
            </p>
          </div>

          <p className="honesty">
            <b>Honesty note.</b> Idealised <b>circular</b> orbits with secular <b>J2</b> nodal
            precession — no drag, SRP, third-body, manoeuvres, or TLE ingest; this is a design-space
            explorer, not an ephemeris service. Presets are each system's <i>published design
            parameters</i> (primary shell only). Coverage is an area-weighted grid statistic; link
            budget, spectrum, inter-satellite links and capacity are out of scope. Constants are
            WGS-84/EGM-96. Every headline number is reproduced by <code>node verify.mjs</code>.
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
