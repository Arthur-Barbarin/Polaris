/**
 * Monte Carlo profit distribution — 2,000 draws over plausible input ranges
 * (triangular distributions). Reports P10 / P50 / P90 annual profit and the
 * probability the route is profitable. This is the chart an investor wants:
 * the point-estimate metrics elsewhere hide tail risk.
 */
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Cell, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { fmt_usd, fmt_pct } from '../models/economics.js';

const fmtCompact = (v) => {
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000)     return `$${Math.round(v / 1000)}k`;
  return `$${Math.round(v)}`;
};

const Stat = ({ label, value, color = '#c8d0e8' }) => (
  <div>
    <div style={{ fontSize: 10, color: '#3a4060', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</div>
    <div style={{ fontSize: 15, fontWeight: 700, color, marginTop: 2 }}>{value}</div>
  </div>
);

export default function MonteCarloChart({ mc }) {
  const probColor = mc.prob_profitable >= 0.70 ? '#2DBD7E'
                  : mc.prob_profitable >= 0.40 ? '#E8813A' : '#E85C5C';

  return (
    <div className="panel">
      <div className="chart-title">Profit distribution — Monte Carlo</div>
      <div className="chart-sub">
        {mc.n_draws.toLocaleString()} draws over fare, load factor, electricity, deadhead,
        demand, availability, and landing fee (triangular ranges around current inputs).
      </div>

      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 12,
      }}>
        <Stat label="P10 (downside)" value={fmt_usd(mc.p10)} color={mc.p10 < 0 ? '#E85C5C' : '#c8d0e8'} />
        <Stat label="P50 (median)" value={fmt_usd(mc.p50)} color={mc.p50 < 0 ? '#E85C5C' : '#c8d0e8'} />
        <Stat label="P90 (upside)" value={fmt_usd(mc.p90)} color={mc.p90 < 0 ? '#E85C5C' : '#2DBD7E'} />
        <Stat label="P(profit)" value={fmt_pct(mc.prob_profitable, 0)} color={probColor} />
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={mc.bins} margin={{ top: 4, right: 16, left: 4, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e2535" vertical={false} />
          <XAxis
            dataKey="mid"
            type="number"
            domain={[mc.min, mc.max]}
            tick={{ fill: '#5a6080', fontSize: 10 }}
            tickFormatter={fmtCompact}
            ticks={[mc.min, mc.p10, mc.p50, mc.p90, mc.max]}
          />
          <YAxis
            tick={{ fill: '#5a6080', fontSize: 10 }}
            label={{ value: 'draws', angle: -90, position: 'insideLeft', offset: 14, fill: '#5a6080', fontSize: 10 }}
          />
          <Tooltip
            cursor={{ fill: 'rgba(74,144,217,0.08)' }}
            contentStyle={{ background: '#131720', border: '1px solid #1e2535', borderRadius: 8, fontSize: 11 }}
            labelFormatter={(v) => `Profit ${fmtCompact(v)}`}
            formatter={(value) => [value, 'draws']}
          />
          <ReferenceLine x={0} stroke="#3a4060" strokeWidth={1.5} label={{ value: 'breakeven', fill: '#5a6080', fontSize: 9, position: 'top' }} />
          <ReferenceLine x={mc.p50} stroke="#4A90D9" strokeDasharray="3 3" />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {mc.bins.map((b, i) => (
              <Cell
                key={i}
                fill={b.mid < 0 ? '#E85C5C' : '#2DBD7E'}
                fillOpacity={0.55}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div className="source-line">
        Triangular distributions: fare ±25%, LF ±15pp, electricity ±30%, deadhead ±10pp,
        demand ±20pp, availability ±10pp, landing ±50%. Seeded draws — stable across renders.
      </div>
    </div>
  );
}
