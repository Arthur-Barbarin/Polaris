import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine,
} from "recharts";

export default function ScalingChart({ rows, knee }) {
  return (
    <div className="chart-wrap">
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={rows} margin={{ top: 14, right: 12, left: -8, bottom: 46 }}>
          <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
          <XAxis dataKey="n" stroke="#64748b" fontSize={11} tickMargin={6}
                 label={{ value: "fleet size (airborne ops)", position: "insideBottom", offset: -20, fill: "#64748b", fontSize: 11 }} />
          <YAxis yAxisId="l" stroke="#64748b" fontSize={11} />
          <YAxis yAxisId="r" orientation="right" stroke="#64748b" fontSize={11} />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
            labelStyle={{ color: "#e2e8f0" }}
          />
          <Legend verticalAlign="bottom" height={30} iconSize={10}
                  wrapperStyle={{ fontSize: 11, paddingTop: 30 }} />
          <Bar yAxisId="l" dataKey="baselineConflicts" name="conflicts (pre-deconfliction)" fill="#f43f5e" opacity={0.6} />
          <Line yAxisId="r" dataKey="delayMean_min" name="mean delay (min)" stroke="#38bdf8" dot={false} strokeWidth={2} />
          <Line yAxisId="l" dataKey="residual" name="unresolved" stroke="#f59e0b" dot={false} strokeWidth={2} />
          {knee && (
            <ReferenceLine yAxisId="l" x={knee} stroke="#f59e0b" strokeDasharray="5 3"
                           label={{ value: `knee ≈ ${knee}`, fill: "#f59e0b", fontSize: 11, position: "insideTopLeft", offset: 6 }} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
