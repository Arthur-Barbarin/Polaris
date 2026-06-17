/**
 * Sensitivity tornado — redesigned for clarity:
 * - Single bar per input (net impact of +20% change, direction-corrected)
 * - Green = +20% of this input improves profit | Red = hurts profit
 * - Sorted by absolute impact (highest leverage at top)
 * - Plain-language axis label
 */
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer, ReferenceLine } from 'recharts';
import { fmt_usd } from '../models/economics.js';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  const sign = d.net_impact >= 0 ? '+' : '';
  return (
    <div style={{ background: '#131720', border: '1px solid #1e2535', borderRadius: 8, padding: '10px 14px', fontSize: 12 }}>
      <div style={{ color: '#7a8099', marginBottom: 4 }}>{label}</div>
      <div style={{ color: d.net_impact >= 0 ? '#2DBD7E' : '#E85C5C', fontWeight: 600 }}>
        {sign}{fmt_usd(d.net_impact)} / year if +20%
      </div>
      <div style={{ color: '#5a6080', fontSize: 11, marginTop: 3 }}>
        {d.net_impact >= 0
          ? 'Increasing this input improves profit'
          : 'Increasing this input reduces profit'}
      </div>
    </div>
  );
};

export default function SensitivityChart({ sensitivity }) {
  // For each input, compute: "if this input goes up 20%, what happens to profit?"
  // direction: 'up_good' means +20% → profit goes up (green)
  //            'down_good' means +20% → profit goes down (red)
  const data = sensitivity.slice(0, 7).map(s => ({
    ...s,
    // net_impact = change in profit when input goes +20%
    net_impact: s.impact_up,
    display_impact: Math.abs(s.impact_up),
  }));

  const maxAbs = Math.max(...data.map(d => d.display_impact));
  // Add 30% padding so bars never hit the chart edge
  const xDomain = [-maxAbs * 1.35, maxAbs * 1.35];

  return (
    <div className="panel">
      <div className="chart-title">Leverage ranking</div>
      <div className="chart-sub">
        Change in annual profit if each input increases by 20% — sorted by impact. Green = increase helps profit. Red = increase hurts profit.
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 0, right: 70, left: 115, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#1e2535" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fill: '#5a6080', fontSize: 10 }}
            tickFormatter={v => `${v >= 0 ? '+' : ''}$${(v / 1000).toFixed(0)}k`}
            domain={xDomain}
          />
          <YAxis
            type="category"
            dataKey="label"
            tick={{ fill: '#9aa0b8', fontSize: 11 }}
            width={115}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine x={0} stroke="#3a4060" strokeWidth={1.5} />

          <Bar
            dataKey="net_impact"
            radius={[0, 4, 4, 0]}
            maxBarSize={22}
            label={{
              position: 'right',
              formatter: v => `${v >= 0 ? '+' : ''}$${Math.round(Math.abs(v) / 1000)}k`,
              fill: '#5a6080',
              fontSize: 10,
            }}
          >
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.net_impact >= 0 ? '#2DBD7E' : '#E85C5C'}
                fillOpacity={0.85}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div className="source-line">±20% single-variable perturbation. All other inputs held constant. Pilot cost shown only for piloted vehicles.</div>
    </div>
  );
}
