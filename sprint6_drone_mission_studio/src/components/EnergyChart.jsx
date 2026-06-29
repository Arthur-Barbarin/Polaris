// Wind-sensitivity chart: how does mission energy / margin change vs headwind?
// X-axis: headwind component (m/s), -10 (tailwind) to drone.cruise-1 (limit).
// Y-axis (left): Wh used. Reference line: usable Wh.

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
  Legend,
} from "recharts";
import { missionEnergy } from "../models/energy.js";

export default function EnergyChart({ drone, distance_m, currentHeadwind_ms }) {
  if (!drone || distance_m <= 0) return null;
  const data = [];
  const upper = Math.min(drone.cruise_ms - 1, 15);
  for (let h = -10; h <= upper; h += 1) {
    const r = missionEnergy(drone, distance_m, h, 0);
    data.push({
      headwind: h,
      wh: r.energy_wh != null ? +r.energy_wh.toFixed(1) : null,
      time_min: +(r.time_s / 60).toFixed(1),
    });
  }
  const usable = drone.battery_wh ? +(drone.battery_wh * 0.85).toFixed(1) : null;
  return (
    <div className="chart-wrap">
      <div className="chart-title">
        Wind sensitivity — mission energy vs headwind component
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid stroke="#eee" strokeDasharray="3 3" />
          <XAxis
            dataKey="headwind"
            type="number"
            label={{
              value: "headwind component (m/s) — negative = tailwind",
              position: "insideBottom",
              offset: -4,
              style: { fontSize: 10 },
            }}
            tick={{ fontSize: 10 }}
          />
          <YAxis
            label={{
              value: "energy (Wh)",
              angle: -90,
              position: "insideLeft",
              style: { fontSize: 10 },
            }}
            tick={{ fontSize: 10 }}
          />
          <Tooltip
            formatter={(v, name) =>
              name === "wh" ? [`${v} Wh`, "Energy"] : [`${v} min`, "Time"]
            }
            labelFormatter={(l) => `${l} m/s headwind`}
          />
          {usable && (
            <ReferenceLine
              y={usable}
              stroke="#ef4444"
              strokeDasharray="4 4"
              label={{
                value: `Usable: ${usable} Wh`,
                fontSize: 10,
                fill: "#ef4444",
              }}
            />
          )}
          <ReferenceLine
            x={currentHeadwind_ms}
            stroke="#0066ff"
            strokeDasharray="3 3"
            label={{
              value: "current",
              position: "top",
              fontSize: 10,
              fill: "#0066ff",
            }}
          />
          <Line
            type="monotone"
            dataKey="wh"
            stroke="#0066ff"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
