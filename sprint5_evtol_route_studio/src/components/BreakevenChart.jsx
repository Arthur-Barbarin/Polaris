import {
  ComposedChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ReferenceArea, ResponsiveContainer,
} from 'recharts';
import { fmt_usd } from '../models/economics.js';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const profit = payload.find(p => p.dataKey === 'annual_profit')?.value;
  return (
    <div style={{ background: '#131720', border: '1px solid #1e2535', borderRadius: 8, padding: '10px 14px', fontSize: 12 }}>
      <div style={{ color: '#7a8099', marginBottom: 4 }}>Load factor: {label}%</div>
      <div style={{ color: profit >= 0 ? '#2DBD7E' : '#E85C5C', fontWeight: 600 }}>
        {profit >= 0 ? '+' : ''}{fmt_usd(profit, 0)} / year
      </div>
    </div>
  );
};

export default function BreakevenChart({ curve, currentLF, breakevenLF, vehicle }) {
  const beLFpct = Math.round(Math.min(breakevenLF, 1) * 100);
  const currentLFpct = Math.round(currentLF * 100);

  const profits = curve.map(p => p.annual_profit);
  const maxP = Math.max(...profits);
  const minP = Math.min(...profits);
  // Symmetric domain with 15% headroom
  const range = Math.max(Math.abs(maxP), Math.abs(minP)) * 1.15;
  const yDomain = [-range, range];

  return (
    <div className="panel">
      <div className="chart-title">Break-even curve</div>
      <div className="chart-sub">
        Annual profit per aircraft vs load factor.
        {' '}<span style={{ color: '#E85C5C' }}>Red zone</span> = loss.
        {' '}<span style={{ color: '#2DBD7E' }}>Green zone</span> = profit.
      </div>

      <ResponsiveContainer width="100%" height={230}>
        <ComposedChart data={curve} margin={{ top: 8, right: 16, left: 10, bottom: 18 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1a2030" />

          {/* Loss zone */}
          <ReferenceArea
            x1={0} x2={beLFpct}
            y1={yDomain[0]} y2={0}
            fill="#E85C5C" fillOpacity={0.06}
          />
          {/* Profit zone */}
          <ReferenceArea
            x1={beLFpct} x2={100}
            y1={0} y2={yDomain[1]}
            fill="#2DBD7E" fillOpacity={0.06}
          />

          <XAxis
            dataKey="load_factor_pct"
            tick={{ fill: '#5a6080', fontSize: 11 }}
            tickFormatter={v => `${v}%`}
            label={{ value: 'Load factor', position: 'insideBottom', offset: -10, fill: '#5a6080', fontSize: 11 }}
          />
          <YAxis
            tick={{ fill: '#5a6080', fontSize: 11 }}
            tickFormatter={v => `$${(v / 1000).toFixed(0)}k`}
            domain={yDomain}
            width={50}
          />
          <Tooltip content={<CustomTooltip />} />

          {/* Zero line */}
          <ReferenceLine y={0} stroke="#3a4060" strokeWidth={1.5} />

          {/* Break-even line */}
          {isFinite(breakevenLF) && breakevenLF <= 1 && (
            <ReferenceLine
              x={beLFpct}
              stroke="#E8813A"
              strokeDasharray="5 3"
              label={{
                value: `B/E ${beLFpct}%`,
                fill: '#E8813A', fontSize: 10,
                position: beLFpct > 50 ? 'insideTopLeft' : 'insideTopRight',
              }}
            />
          )}

          {/* Current load factor */}
          <ReferenceLine
            x={currentLFpct}
            stroke={vehicle.color}
            strokeDasharray="3 3"
            strokeOpacity={0.7}
            label={{
              value: `Now ${currentLFpct}%`,
              fill: vehicle.color, fontSize: 10,
              position: currentLFpct > 50 ? 'insideBottomLeft' : 'insideBottomRight',
            }}
          />

          <Area
            type="monotone"
            dataKey="annual_profit"
            stroke={vehicle.color}
            strokeWidth={2}
            fill={vehicle.color}
            fillOpacity={0.07}
            dot={false}
            activeDot={{ r: 4, fill: vehicle.color }}
          />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="source-line">Break-even = load factor where annual revenue covers opex + annualized capex</div>
    </div>
  );
}
