import { useMemo, useState } from "react";
import MapView from "./components/MapView.jsx";
import Sidebar from "./components/Sidebar.jsx";
import VerdictPanel from "./components/VerdictPanel.jsx";
import EnergyChart from "./components/EnergyChart.jsx";
import { DRONES } from "./data/drones.js";
import { NO_FLY_PRESETS } from "./data/no_fly.js";
import { planRoute, pathDistance_m } from "./models/planner.js";
import {
  missionEnergy,
  headwindComponent,
  pathBearing,
} from "./models/energy.js";
import { riskExposure } from "./models/risk.js";
import { checkCompliance } from "./models/regulatory.js";

// Defaults: a Seattle Center → Bellevue Square inspection corridor.
// Crosses Lake Washington — good for showing wind sensitivity over open water.
const DEFAULT_START = { lat: 47.6205, lng: -122.3493 };
const DEFAULT_GOAL = { lat: 47.6172, lng: -122.2017 };

export default function App() {
  const [droneId, setDroneId] = useState("skydio_x10");
  const [start, setStart] = useState(DEFAULT_START);
  const [goal, setGoal] = useState(DEFAULT_GOAL);
  const [clickMode, setClickMode] = useState("start");
  const [conditions, setConditions] = useState({
    windSpeed: 4,
    windFrom: 270,
    payloadKg: 0,
    hoverMin: 2,
    vlos: true,
    controlled: false,
    overPeople: false,
    night: false,
  });
  // Mission altitude is fixed at 200 ft AGL — well within Part 107 ceiling.
  // At sUAS altitudes (0–500 ft) climb energy (~0.5 Wh) and density derating
  // (~1%) are negligible vs wind/payload effects, so we don't expose it.
  const MISSION_ALTITUDE_FT = 200;
  const [noFlyToggles, setNoFlyToggles] = useState(
    Object.fromEntries(NO_FLY_PRESETS.map((p) => [p.id, p.enabled_by_default]))
  );

  const drone = DRONES[droneId];

  const noFlyPolys = useMemo(
    () => NO_FLY_PRESETS.filter((p) => noFlyToggles[p.id]),
    [noFlyToggles]
  );
  const noFlyPolygons = noFlyPolys.map((p) => p.polygon);

  const planResult = useMemo(
    () =>
      start && goal
        ? planRoute({ start, goal, noFlyPolys: noFlyPolygons })
        : { path: [], found: false },
    [start, goal, noFlyPolygons]
  );

  const distance_m = useMemo(
    () => pathDistance_m(planResult.path),
    [planResult.path]
  );

  const headwind_ms = useMemo(() => {
    if (!start || !goal) return 0;
    const bearing = pathBearing(start, goal);
    return headwindComponent(conditions.windSpeed, conditions.windFrom, bearing);
  }, [start, goal, conditions.windSpeed, conditions.windFrom]);

  const energy = useMemo(
    () =>
      missionEnergy(
        drone,
        distance_m,
        headwind_ms,
        conditions.hoverMin * 60,
        conditions.payloadKg
      ),
    [drone, distance_m, headwind_ms, conditions.hoverMin, conditions.payloadKg]
  );

  const risk = useMemo(() => riskExposure(planResult.path), [planResult.path]);

  const compliance = useMemo(
    () =>
      checkCompliance({
        drone,
        max_altitude_ft: MISSION_ALTITUDE_FT,
        vlos: conditions.vlos,
        controlled_airspace: conditions.controlled,
        over_people: conditions.overPeople,
        night: conditions.night,
      }),
    [drone, conditions]
  );

  const onMapClick = (pt) => {
    if (clickMode === "start") {
      setStart(pt);
      setClickMode("goal");
    } else {
      setGoal(pt);
      setClickMode("start");
    }
  };

  return (
    <div className="app">
      <Sidebar
        droneId={droneId}
        setDroneId={setDroneId}
        conditions={conditions}
        setConditions={setConditions}
        noFlyToggles={noFlyToggles}
        setNoFlyToggles={setNoFlyToggles}
        presets={NO_FLY_PRESETS}
        clickMode={clickMode}
        setClickMode={setClickMode}
        onReset={() => {
          setStart(DEFAULT_START);
          setGoal(DEFAULT_GOAL);
        }}
      />
      <main className="main">
        <div className="map-area">
          <MapView
            start={start}
            goal={goal}
            path={planResult.path}
            noFlyPolys={noFlyPolys}
            onMapClick={onMapClick}
          />
          <div className="map-hint">
            Click the map to {clickMode === "start" ? "set start" : "set goal"}.
            Headwind component: <b>{headwind_ms.toFixed(1)} m/s</b>
            {headwind_ms > drone.wind_limit_ms && (
              <span className="hint-warn">
                {" "}
                · exceeds {drone.name} wind limit ({drone.wind_limit_ms} m/s)
              </span>
            )}
          </div>
        </div>
        <div className="bottom">
          <VerdictPanel
            energy={energy}
            risk={risk}
            compliance={compliance}
            pathFound={planResult.found}
            distance_m={distance_m}
          />
          <EnergyChart
            drone={drone}
            distance_m={distance_m}
            currentHeadwind_ms={headwind_ms}
            payloadKg={conditions.payloadKg}
          />
        </div>
      </main>
    </div>
  );
}
