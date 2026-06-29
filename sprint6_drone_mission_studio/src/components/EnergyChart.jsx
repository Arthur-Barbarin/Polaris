// Wind-sensitivity chart: how does mission energy / margin change vs headwind?
// X-axis: headwind component (m/s).  Y-axis: Wh used.
// Reference lines: usable Wh (horizontal, red dashed) and current headwind
// (vertical, blue dashed). Labels placed outside the plot area so they don't
// collide with the curve or each other.

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import { missionEnergy } from "../models/energy.js";

export default function EnergyChart({ drone, distance_m, currentHeadwind_ms, payloadKg = 0 }) {
  if (!drone || distance_m <= 0) return null;

  const upper = Math.min(drone.cruise_ms - 1, 15);
  const data = [];
  for (let h = -10; h <= upper; h += 1) {
    const r = missionEnergy(drone, distance_m, h, 0, payloadKg);
    data.push({
      headwind: h,
      wh: r.energy_wh != null ? +r.energy_wh.toFixed(1) : null,
    });
  }
  const usable = drone.battery_wh ? +(drone.battery_wh * 0.85).toFixed(1) : null;

  // Cap Y-axis at 1.5× usable so the asymptotic blow-up doesn't squash detail
  const yMax = usable ? Math.max(usable * 1.5, ...data.map(d => d.wh ?? 0).filter(v => v < usable * 2)) : "auto";

  return (
    <div className="chart-wrap">
      <div className="chart-title">
        Wind sensitivity — mission energy vs headwind component
      </div>
      <ResponsiveContainer width="100%" height={210}>
        <LineChart
          data={data}
          margin={{ top: 18, right: 24, left: 44, bottom: 28 }}
        >
          <CartesianGrid stroke="#eee" strokeDasharray="3 3" />
          <XAxis
            dataKey="headwind"
            type="number"
            domain={[-10, upper]}
            ticks={[-10, -5, 0, 5, 10].filter(t => t <= upper)}
            label={{
              value: "headwind component (m/s) — negative = tailwind",
              position: "insideBottom",
              offset: -10,
              style: { fontSize: 10, fill: "#64748b" },
            }}
            tick={{ fontSize: 10 }}
          />
          <YAxis
            domain={[0, yMax]}
            label={{
              value: "energy (Wh)",
              angle: -90,
              position: "left",
              offset: 0,
              style: { fontSize: 10, fill: "#64748b", textAnchor: "middle" },
            }}
            tick={{ fontSize: 10 }}
          />
          <Tooltip
            formatter={(v) => [`${v} Wh`, "Energy"]}
            labelFormatter={(l) => `${l} m/s headwind`}
            contentStyle={{ fontSize: 11 }}
          />
          {usable && (
            <ReferenceLine
              y={usable}
              stroke="#ef4444"
              strokeDasharray="4 4"
              label={{
                value: `usable ${usable} Wh`,
                position: "insideTopRight",
                fontSize: 10,
                fill: "#ef4444",
                offset: 4,
              }}
            />
          )}
          <ReferenceLine
            x={currentHeadwind_ms}
            stroke="#0066ff"
            strokeDasharray="3 3"
            label={{
              value: "current",
              position: "insideTopLeft",
              fontSize: 10,
              fill: "#0066ff",
              offset: 4,
            }}
          />
          <Line
            type="monotone"
            dataKey="wh"
            stroke="#0066ff"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
