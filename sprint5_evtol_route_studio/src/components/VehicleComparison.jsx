import { VEHICLES } from '../data/vehicles.js';
import { computeEconomics, fmt_usd, fmt_pct } from '../models/economics.js';
import { useMemo } from 'react';

const NAMED_VEHICLES = ['joby_s4', 'archer_midnight', 'wisk_gen6'];

export default function VehicleComparison({ route, ops, activeVehicleId }) {
  const results = useMemo(() =>
    NAMED_VEHICLES.map(id => ({
      vehicle: VEHICLES[id],
      result: computeEconomics(VEHICLES[id], route, ops),
    })),
    [route, ops]
  );

  return (
    <div className="panel">
      <div className="chart-title">Vehicle comparison</div>
      <div className="chart-sub">All three vehicles on your current route & ops settings</div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        {results.map(({ vehicle, result }) => {
          const beLF = result.breakeven_load_factor;
          // Only highlight as active if user selected this named vehicle (not custom)
        const isActive = vehicle.id === activeVehicleId && activeVehicleId !== 'custom';
          const status = beLF > 1.0 ? 'unviable' : beLF > 0.85 ? 'high' : beLF > 0.70 ? 'marginal' : 'viable';
          const statusColor = status === 'viable' ? '#2DBD7E' : status === 'marginal' ? '#C8AA2D' : status === 'high' ? '#E8813A' : '#E85C5C';
          const statusLabel = status === 'viable' ? '✓ Viable' : status === 'marginal' ? '⚠ Marginal' : '✗ Unviable';

          return (
            <div key={vehicle.id} style={{
              background: isActive ? `${vehicle.color}12` : '#0f1420',
              border: `1px solid ${isActive ? vehicle.color : '#252d40'}`,
              borderRadius: 8,
              padding: '12px 14px',
              position: 'relative',
            }}>
              {isActive && (
                <div style={{
                  position: 'absolute', top: 6, right: 8,
                  fontSize: 9, color: vehicle.color, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase',
                }}>active</div>
              )}
              <div style={{ fontSize: 13, fontWeight: 700, color: isActive ? vehicle.color : '#c8d0e8', marginBottom: 2 }}>
                {vehicle.name}
              </div>
              <div style={{ fontSize: 10, color: '#5a6080', marginBottom: 10 }}>
                {vehicle.seats_passenger}p · {vehicle.piloted ? 'Piloted' : 'Autonomous'}
              </div>

              <Row label="B/E load factor" value={
                isFinite(beLF) ? (beLF * 100).toFixed(1) + '%' : '∞'
              } color={statusColor} />
              <Row label="Annual profit" value={
                isFinite(result.annual_profit) ? fmt_usd(result.annual_profit) : '—'
              } color={result.annual_profit >= 0 ? '#2DBD7E' : '#E85C5C'} />
              <Row label="CASM" value={`$${result.casm.toFixed(2)}`} />
              <Row label="Payback" value={
                isFinite(result.payback_years) ? `${result.payback_years.toFixed(1)} yr` : '∞'
              } />
              {!result.range_feasible && (
                <div style={{ marginTop: 8, fontSize: 10, color: '#E85C5C', fontWeight: 600 }}>
                  ✗ Range infeasible ({vehicle.max_range_segment_km} km limit)
                </div>
              )}
              {result.range_feasible && (
                <div style={{
                  marginTop: 10, paddingTop: 8, borderTop: '1px solid #1e2535',
                  fontSize: 11, fontWeight: 600, color: statusColor,
                }}>
                  {statusLabel}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="source-line">Same route & ops settings applied to all vehicles</div>
    </div>
  );
}

function Row({ label, value, color = '#c8d0e8' }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 5 }}>
      <span style={{ fontSize: 10, color: '#5a6080' }}>{label}</span>
      <span style={{ fontSize: 12, fontWeight: 600, color }}>{value}</span>
    </div>
  );
}
