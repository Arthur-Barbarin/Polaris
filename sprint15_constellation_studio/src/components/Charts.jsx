import {
  AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";

const axis = { stroke: "#64748b", fontSize: 11 };
const tip = {
  contentStyle: { background: "#0f172a", border: "1px solid #334155", fontSize: 12 },
  labelStyle: { color: "#e2e8f0" },
};

// Coverage vs constellation size — the "how many satellites do I need" chart.
export function SweepChart({ rows, knee }) {
  return (
    <ResponsiveContainer width="100%" height={210}>
      <AreaChart data={rows} margin={{ top: 10, right: 10, left: -12, bottom: 30 }}>
        <defs>
          <linearGradient id="cov" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.55} />
            <stop offset="100%" stopColor="#38bdf8" stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
        <XAxis dataKey="n" {...axis} tickMargin={6}
               label={{ value: "satellites in constellation", position: "insideBottom", offset: -16, fill: "#64748b", fontSize: 11 }} />
        <YAxis {...axis} domain={[0, 100]} unit="%" />
        <Tooltip {...tip} formatter={(v) => [`${v.toFixed(1)}%`, "global coverage"]} />
        <Area dataKey="coverage" stroke="#38bdf8" strokeWidth={2} fill="url(#cov)" />
        {knee && (
          <ReferenceLine x={knee} stroke="#f59e0b" strokeDasharray="5 3"
                         label={{ value: `continuous ≈ ${knee}`, fill: "#f59e0b", fontSize: 11, position: "insideTopLeft", offset: 6 }} />
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
}

// Coverage as a function of latitude — shows why a 53° shell misses the poles.
export function LatBandChart({ bands }) {
  const data = bands.map((b) => ({ lat: b.lat, coverage: b.coverage * 100 }));
  return (
    <ResponsiveContainer width="100%" height={170}>
      <LineChart data={data} margin={{ top: 10, right: 10, left: -12, bottom: 26 }}>
        <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
        <XAxis dataKey="lat" {...axis} tickMargin={6}
               label={{ value: "latitude (°)", position: "insideBottom", offset: -14, fill: "#64748b", fontSize: 11 }} />
        <YAxis {...axis} domain={[0, 100]} unit="%" />
        <Tooltip {...tip} formatter={(v) => [`${v.toFixed(0)}%`, "covered"]}
                 labelFormatter={(l) => `lat ${l}°`} />
        <Line dataKey="coverage" stroke="#a78bfa" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
