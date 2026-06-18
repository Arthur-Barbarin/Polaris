/**
 * Sensitivity tornado — redesigned for clarity:
 * - Single bar per input (net impact of +20% change, direction-corrected)
 * - Green = +20% of this input improves profit | Red = hurts profit
 * - Sorted by absolute impact (highest leverage at top)
 * - Plain-language axis label
 */
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer, ReferenceLine } from 'recharts';
import { fmt_usd } from '../models/economics.js';

const NOTE_TEXT = {
  lf_equiv: 'Fare and load factor are mathematically equivalent revenue levers (both scale revenue by the same factor) — their bars will always match.',
  margin_dep: 'Sign depends on per-flight margin. When flights are unit-profitable, more flying helps; when unit-unprofitable, more flying hurts.',
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  const sign = d.net_impact >= 0 ? '+' : '';
  return (
    <div style={{ background: '#131720', border: '1px solid #1e2535', borderRadius: 8, padding: '10px 14px', fontSize: 12, maxWidth: 260 }}>
      <div style={{ color: '#7a8099', marginBottom: 4 }}>{label}</div>
      <div style={{ color: d.net_impact >= 0 ? '#2DBD7E' : '#E85C5C', fontWeight: 600 }}>
        {sign}{fmt_usd(d.net_impact)} / year if +20%
      </div>
      <div style={{ color: '#5a6080', fontSize: 11, marginTop: 3 }}>
        {d.net_impact >= 0
          ? 'Increasing this input improves profit'
          : 'Increasing this input reduces profit'}
      </div>
      {d.clamped && (
        <div style={{ color: '#E8813A', fontSize: 10, marginTop: 4, fontStyle: 'italic' }}>
          Clamped at physical bound (e.g. LF ≤ 100%)
        </div>
      )}
      {d.asymmetric && (
        <div style={{ color: '#E8813A', fontSize: 10, marginTop: 4, lineHeight: 1.4 }}>
          ↕ Asymmetric leverage — −20% direction:{' '}
          <strong>{d.impact_down >= 0 ? '+' : ''}{fmt_usd(d.impact_down)}</strong>{' '}
          (bigger than +20% shown).
        </div>
      )}
      {d.note && NOTE_TEXT[d.note] && (
        <div style={{ color: '#9aa0b8', fontSize: 10, marginTop: 6, lineHeight: 1.4 }}>
          ⓘ {NOTE_TEXT[d.note]}
        </div>
      )}
    </div>
  );
};

export default function SensitivityChart({ sensitivity }) {
  // Show ALL inputs — slicing to the top N caused bars to vanish/reappear
  // as input rankings shuffled with route changes, which looked like a bug.
  const data = sensitivity.map(s => ({
    ...s,
    net_impact: s.impact_up,
    display_impact: Math.abs(s.impact_up),
  }));

  const maxAbs = Math.max(...data.map(d => d.display_impact), 1);
  const xDomain = [-maxAbs * 1.35, maxAbs * 1.35];
  // Chart height scales with input count so bars stay readable
  const chartHeight = Math.max(240, data.length * 28);

  return (
    <div className="panel">
      <div className="chart-title">Leverage ranking</div>
      <div className="chart-sub">
        Change in annual profit if each input increases by 20% — sorted by impact. Green = increase helps profit. Red = increase hurts profit.
      </div>

      <ResponsiveContainer width="100%" height={chartHeight}>
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
              formatter: (v, entry) => {
                const sign = v >= 0 ? '+' : '';
                const marker = entry?.asymmetric ? ' ↕' : '';
                return `${sign}$${Math.round(Math.abs(v) / 1000)}k${marker}`;
              },
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

      <div className="source-line">±20% single-variable perturbation, clamped at physical bounds (LF, availability, demand ≤ 100%). All other inputs held constant. Pilot cost shown only for piloted vehicles. Fare ≡ LF (same revenue lever). Bars marked ↕ have a larger −20% impact than +20%.</div>
    </div>
  );
}
