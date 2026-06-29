import { DRONE_LIST } from "../data/drones.js";

export default function Sidebar({
  droneId,
  setDroneId,
  conditions,
  setConditions,
  noFlyToggles,
  setNoFlyToggles,
  presets,
  clickMode,
  setClickMode,
  onReset,
}) {
  const set = (k, v) => setConditions({ ...conditions, [k]: v });
  const drone = DRONE_LIST.find((d) => d.id === droneId);

  return (
    <div className="sidebar">
      <div className="brand">
        <div className="brand-title">Polaris</div>
        <div className="brand-sub">Drone Mission Studio</div>
      </div>

      <section>
        <h3>Drone</h3>
        <select
          value={droneId}
          onChange={(e) => setDroneId(e.target.value)}
          className="full"
        >
          {DRONE_LIST.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name} — {d.role}
            </option>
          ))}
        </select>
        <div className="specs">
          <div>
            <span>MTOW</span>
            <b>{drone.mtow_kg} kg</b>
          </div>
          <div>
            <span>Battery</span>
            <b>{drone.battery_wh ? `${drone.battery_wh} Wh` : "n/a"}</b>
          </div>
          <div>
            <span>Endurance</span>
            <b>{drone.max_flight_time_min} min</b>
          </div>
          <div>
            <span>Cruise</span>
            <b>{drone.cruise_ms} m/s</b>
          </div>
          <div>
            <span>Wind limit</span>
            <b>{drone.wind_limit_ms} m/s</b>
          </div>
          <div>
            <span>Remote ID</span>
            <b>{drone.has_rid ? "✓" : "✗"}</b>
          </div>
        </div>
      </section>

      <section>
        <h3>Click mode</h3>
        <div className="seg">
          <button
            className={clickMode === "start" ? "on" : ""}
            onClick={() => setClickMode("start")}
          >
            Set start
          </button>
          <button
            className={clickMode === "goal" ? "on" : ""}
            onClick={() => setClickMode("goal")}
          >
            Set goal
          </button>
        </div>
        <button className="ghost full" onClick={onReset}>
          Reset waypoints
        </button>
      </section>

      <section>
        <h3>Environment</h3>
        <label>
          Wind speed: <b>{conditions.windSpeed} m/s</b>
          <input
            type="range"
            min="0"
            max="20"
            step="0.5"
            value={conditions.windSpeed}
            onChange={(e) => set("windSpeed", parseFloat(e.target.value))}
          />
        </label>
        <label>
          Wind from: <b>{conditions.windFrom}°</b>
          <input
            type="range"
            min="0"
            max="359"
            step="1"
            value={conditions.windFrom}
            onChange={(e) => set("windFrom", parseInt(e.target.value))}
          />
        </label>
        <label>
          Payload: <b>{conditions.payloadKg.toFixed(1)} kg</b>
          {(() => {
            const maxPayload = drone.payload_kg ?? drone.mtow_kg * 0.4;
            return (
              <input
                type="range"
                min="0"
                max={maxPayload}
                step="0.1"
                value={Math.min(conditions.payloadKg, maxPayload)}
                onChange={(e) => set("payloadKg", parseFloat(e.target.value))}
              />
            );
          })()}
          <small style={{ color: "var(--muted)", fontSize: 10, display: "block", marginTop: 2 }}>
            Hover power scales as W^1.5 — heavier load shrinks the corridor.
          </small>
        </label>
        <label>
          Hover time (inspection): <b>{conditions.hoverMin} min</b>
          <input
            type="range"
            min="0"
            max="20"
            step="0.5"
            value={conditions.hoverMin}
            onChange={(e) => set("hoverMin", parseFloat(e.target.value))}
          />
        </label>
      </section>

      <section>
        <h3>Operation</h3>
        <label className="row">
          <input
            type="checkbox"
            checked={conditions.vlos}
            onChange={(e) => set("vlos", e.target.checked)}
          />
          VLOS (visual line of sight)
        </label>
        <label className="row">
          <input
            type="checkbox"
            checked={conditions.controlled}
            onChange={(e) => set("controlled", e.target.checked)}
          />
          Controlled airspace (LAANC)
        </label>
        <label className="row">
          <input
            type="checkbox"
            checked={conditions.overPeople}
            onChange={(e) => set("overPeople", e.target.checked)}
          />
          Over people
        </label>
        <label className="row">
          <input
            type="checkbox"
            checked={conditions.night}
            onChange={(e) => set("night", e.target.checked)}
          />
          Night
        </label>
      </section>

      <section>
        <h3>No-fly zones</h3>
        {presets.map((p) => (
          <label key={p.id} className="row">
            <input
              type="checkbox"
              checked={!!noFlyToggles[p.id]}
              onChange={(e) =>
                setNoFlyToggles({ ...noFlyToggles, [p.id]: e.target.checked })
              }
            />
            {p.name}
          </label>
        ))}
      </section>
    </div>
  );
}
