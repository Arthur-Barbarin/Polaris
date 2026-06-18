/**
 * CASM chart — aviation-only benchmarks (Uber Black removed: different cost basis).
 * Shows RASM as a green reference line: above this CASM → profitable per ASM.
 * Highlights where this vehicle sits relative to aviation alternatives.
 */
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Cell, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { BENCHMARKS } from '../data/vehicles.js';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const val = payload[0]?.value;
  return (
    <div style={{ background: '#131720', border: '1px solid #1e2535', borderRadius: 8, padding: '10px 14px', fontSize: 12 }}>
      <div style={{ color: '#7a8099', marginBottom: 4 }}>{label}</div>
      <div style={{ color: '#e8eaf0', fontWeight: 600 }}>${val?.toFixed(2)} / available seat-mile</div>
    </div>
  );
};

export default function CasmChart({ result, vehicle }) {
  // Shorten names for x-axis readability
  const shortName = (name) => name
    .replace('Helicopter charter', 'Heli charter')
    .replace('Helicopter shuttle', 'Heli shuttle')
    .replace('Premium ground (4-seat)', 'Premium ground');

  const data = [
    { name: shortName(vehicle.name), casm: result.casm, color: vehicle.color, isActive: true },
    ...BENCHMARKS.map(b => ({ name: shortName(b.name), casm: b.casm_usd, color: b.color, isActive: false, note: b.note })),
  ].sort((a, b) => b.casm - a.casm);

  const rasm = result.rasm;

  return (
    <div className="panel">
      <div className="chart-title">CASM vs corridor competitors</div>
      <div className="chart-sub">
        <strong>Bars = CASM</strong> (operating cost per available seat-mile).
        Compared against modes that actually compete on UAM trip lengths (5–100 km):
        helicopter operations and premium ground. Long-haul aviation excluded —
        different mission profile, not a competitive set.{' '}
        <span style={{ color: '#2DBD7E' }}>Green line</span> = RASM (revenue / total ASM);
        CASM &lt; RASM ⇒ opex covered.
      </div>

      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 8, right: 20, left: 10, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e2535" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fill: '#9aa0b8', fontSize: 11 }}
            interval={0}
          />
          <YAxis
            tick={{ fill: '#5a6080', fontSize: 10 }}
            tickFormatter={v => `$${v.toFixed(2)}`}
            label={{ value: 'CASM ($/seat-mile)', angle: -90, position: 'insideLeft', offset: 10, dy: 60, fill: '#5a6080', fontSize: 10 }}
          />
          <Tooltip content={<CustomTooltip />} />

          <ReferenceLine
            y={rasm}
            stroke="#2DBD7E"
            strokeWidth={1.5}
            strokeDasharray="5 3"
            label={{ value: `RASM $${rasm.toFixed(2)}`, fill: '#2DBD7E', fontSize: 10, position: 'insideTopRight' }}
          />

          <Bar
            dataKey="casm"
            radius={[4, 4, 0, 0]}
            label={{
              position: 'top',
              formatter: v => `$${v.toFixed(2)}`,
              fill: '#9aa0b8',
              fontSize: 10,
              fontWeight: 600,
            }}
          >
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.isActive ? vehicle.color : entry.color}
                fillOpacity={entry.isActive ? 0.9 : 0.45}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10 }}>
        <div className="source-line" style={{ margin: 0 }}>
          [FAA-HELO] helicopter ops · Blade investor materials · AAA / TNC operating-cost estimates
        </div>
        <div style={{ fontSize: 10, color: result.casm < rasm ? '#2DBD7E' : '#E85C5C', fontWeight: 600 }}>
          {result.casm < rasm
            ? `✓ CASM below RASM — opex covered at current utilization`
            : `✗ CASM exceeds RASM — opex not covered even before capex`}
        </div>
      </div>
    </div>
  );
}
