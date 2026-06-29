export default function VerdictPanel({
  energy,
  risk,
  compliance,
  pathFound,
  distance_m,
  blockers = [],
}) {
  if (!pathFound) {
    return (
      <div className="verdict block">
        <div className="verdict-head">
          <span className="badge block">No route found</span>
        </div>
        {blockers.length > 0 ? (
          <p>
            The planner could not find a route around the active no-fly zones.
            The direct corridor is cut by:
            <ul style={{ margin: "6px 0 0 16px", paddingLeft: 0 }}>
              {blockers.map((b) => (
                <li key={b.id} style={{ fontSize: 12 }}>
                  <b>{b.name}</b>
                </li>
              ))}
            </ul>
            <small style={{ color: "var(--muted)" }}>
              Toggle the offending zone off in the sidebar, or move the
              start/goal so the corridor has a free path.
            </small>
          </p>
        ) : (
          <p>
            The planner could not find a route. Move the start or goal to a
            point with a clearer corridor.
          </p>
        )}
      </div>
    );
  }

  const reasons = [];
  if (!energy.feasible)
    reasons.push(energy.reason || "Energy budget exceeded");
  if (!compliance.allow) reasons.push("Regulatory non-compliance");
  const overall = reasons.length === 0;

  const cls = overall ? "ok" : reasons.length === 1 ? "warn" : "block";

  return (
    <div className={`verdict ${cls}`}>
      <div className="verdict-head">
        <span className={`badge ${cls}`}>
          {overall ? "Mission viable" : "Mission blocked"}
        </span>
        <span className="dist">{(distance_m / 1000).toFixed(2)} km route</span>
      </div>

      <div className="vrow">
        <div className="vlabel">Energy</div>
        <div className="vbody">
          {energy.energy_wh != null ? (
            <>
              <b>{energy.energy_wh.toFixed(1)} Wh</b> /{" "}
              {energy.energy_available_wh.toFixed(1)} Wh usable
              <div className="meter">
                <div
                  className="meter-fill"
                  style={{
                    width: `${Math.min(100, (energy.energy_wh / energy.energy_available_wh) * 100)}%`,
                    background:
                      energy.energy_wh / energy.energy_available_wh > 0.9
                        ? "#ef4444"
                        : energy.energy_wh / energy.energy_available_wh > 0.7
                          ? "#f59e0b"
                          : "#10b981",
                  }}
                />
              </div>
              <small>
                margin {energy.margin_pct.toFixed(0)}% · P̄ ={" "}
                {energy.avg_power_w.toFixed(0)} W · {" "}
                {(energy.time_s / 60).toFixed(1)} min in air · ground speed{" "}
                {energy.ground_speed_ms.toFixed(1)} m/s
              </small>
            </>
          ) : (
            <>
              <b>{energy.range_used_pct?.toFixed(0) ?? "—"}%</b> of published
              range
              <small>
                Battery capacity not published — feasibility via range only.{" "}
                {(energy.time_s / 60).toFixed(1)} min in air, ground speed{" "}
                {energy.ground_speed_ms.toFixed(1)} m/s.
              </small>
            </>
          )}
          {energy.reason && <small className="warn">{energy.reason}</small>}
        </div>
      </div>

      <div className="vrow">
        <div className="vlabel">Population exposure</div>
        <div className="vbody">
          <b>{risk.class}</b> &nbsp;<small>peak density {risk.peak.toFixed(1)}/10 · mean {risk.mean.toFixed(1)}/10</small>
        </div>
      </div>

      <div className="vrow">
        <div className="vlabel">Regulatory</div>
        <div className="vbody">
          {compliance.findings.map((f, i) => (
            <div key={i} className={`finding ${f.level}`}>
              <span className="dot" /> {f.text}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
