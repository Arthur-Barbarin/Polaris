import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine, ReferenceArea,
} from "recharts";

// Accepted operations against requested demand, over `nSeeds` independent
// demand draws. The shaded band is the 10th-90th percentile of accepted
// operations; the dashed diagonal is "everything requested is served".
// Capacity is where the median curve leaves the diagonal — that gap IS the
// answer, and showing it as a band rather than a single line is the point:
// across demand profiles this network's knee moves by roughly +/- 10%.
export default function ScalingChart({ band, kneeMed, kneeP10, kneeP90, serviceLevel }) {
  const rows = band.map((r) => ({
    ...r,
    demand: r.n,
    lo: r.accepted_p10,
    span: r.accepted_p90 - r.accepted_p10,
  }));
  return (
    <div className="chart-wrap">
      <ResponsiveContainer width="100%" height={290}>
        <ComposedChart data={rows} margin={{ top: 14, right: 12, left: -8, bottom: 46 }}>
          <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
          <XAxis dataKey="n" stroke="#64748b" fontSize={11} tickMargin={6} type="number"
                 domain={["dataMin", "dataMax"]}
                 label={{ value: "requested operations in the demand window", position: "insideBottom", offset: -20, fill: "#64748b", fontSize: 11 }} />
          <YAxis yAxisId="l" stroke="#64748b" fontSize={11} />
          <YAxis yAxisId="r" orientation="right" stroke="#64748b" fontSize={11} />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
            labelStyle={{ color: "#e2e8f0" }}
            formatter={(v, name) => [typeof v === "number" ? v.toFixed(1) : v, name]}
          />
          <Legend verticalAlign="bottom" height={30} iconSize={10}
                  wrapperStyle={{ fontSize: 11, paddingTop: 30 }} />

          {kneeP10 != null && kneeP90 != null && (
            <ReferenceArea yAxisId="l" x1={kneeP10} x2={kneeP90} fill="#f59e0b" fillOpacity={0.10} />
          )}

          {/* 10th-90th percentile band, drawn as base + stacked span */}
          <Area yAxisId="l" dataKey="lo" stackId="b" stroke="none" fill="none" legendType="none" name="p10" />
          <Area yAxisId="l" dataKey="span" stackId="b" stroke="none" fill="#38bdf8" fillOpacity={0.18}
                name="accepted, 10th-90th pct" />

          <Line yAxisId="l" dataKey="demand" name="requested (all served)" stroke="#475569"
                strokeDasharray="5 4" dot={false} strokeWidth={1.5} />
          <Line yAxisId="l" dataKey="accepted_med" name="accepted (median)" stroke="#38bdf8"
                dot={false} strokeWidth={2.5} />
          <Line yAxisId="r" dataKey="delay_med" name="mean delay, min (median)" stroke="#a78bfa"
                dot={false} strokeWidth={1.8} />

          {kneeMed != null && (
            <ReferenceLine yAxisId="l" x={kneeMed} stroke="#f59e0b" strokeDasharray="5 3"
                           label={{ value: `capacity ≈ ${Math.round(kneeMed)}`, fill: "#f59e0b", fontSize: 11, position: "insideTopLeft", offset: 6 }} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
      <p className="fine" style={{ marginTop: -6 }}>
        Capacity is stated at a service level: the demand at which the planner can no
        longer accept {Math.round((serviceLevel ?? 0.95) * 100)}% of requested operations.
      </p>
    </div>
  );
}
