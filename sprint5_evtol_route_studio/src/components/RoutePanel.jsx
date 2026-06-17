import { fmt_usd, fmt_pct } from '../models/economics.js'

function Slider({ label, unit, value, min, max, step = 1, onChange, displayFn, highlight }) {
  const display = displayFn ? displayFn(value) : `${value} ${unit}`
  return (
    <div className="field" style={highlight ? {
      background: '#0f1a2a', borderRadius: 8, padding: '10px 12px', marginBottom: 10,
      border: '1px solid #1e3050',
    } : {}}>
      <label style={highlight ? { color: '#c8d0e8' } : {}}>
        {label}
        <span>{unit}</span>
      </label>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        style={highlight ? { accentColor: '#4A90D9' } : {}} />
      <div className="field-value" style={highlight ? { fontSize: 16 } : {}}>{display}</div>
    </div>
  )
}

export default function RoutePanel({ route, setRoute, result }) {
  const set = (key, val) => setRoute(prev => ({ ...prev, [key]: val }))

  return (
    <div className="panel">
      <div className="panel-title">Route</div>

      {/* Primary inputs — visually elevated */}
      <div style={{ marginBottom: 6 }}>
        <div style={{ fontSize: 10, color: '#3a4060', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
          Primary levers
        </div>
        <Slider label="Fare per seat" unit="USD" value={route.fare_per_seat_usd}
          min={20} max={400} step={5} onChange={v => set('fare_per_seat_usd', v)}
          displayFn={v => fmt_usd(v)} highlight />
        <Slider label="Load factor" unit="" value={route.load_factor}
          min={0.1} max={1.0} step={0.01} onChange={v => set('load_factor', v)}
          displayFn={v => fmt_pct(v)} highlight />
      </div>

      <div style={{ fontSize: 10, color: '#3a4060', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
        Route geometry
      </div>
      <Slider label="Segment distance" unit="km" value={route.distance_km}
        min={10} max={300} step={5} onChange={v => set('distance_km', v)} />

      <hr className="divider" style={{ margin: '12px 0' }} />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
        {[
          ['Flight time', `${Math.round(result.flight_time_min)} min`],
          ['Rev / rev. flight', `$${result.revenue_per_flight.toFixed(0)}`],
          ['Cost / flight', `$${result.total_opex_per_flight.toFixed(0)}`],
        ].map(([k, v]) => (
          <div key={k} style={{ background: '#0f1420', borderRadius: 6, padding: '8px 10px' }}>
            <div style={{ fontSize: 10, color: '#3a4060', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{k}</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#c8d0e8', marginTop: 2 }}>{v}</div>
          </div>
        ))}
      </div>
      <div className="note" style={{ marginTop: 6, fontSize: 10 }}>
        Revenue per <em>revenue</em> flight (excludes empty deadhead). Cost is
        per any flight — denominators differ because deadhead generates cost
        without revenue.
      </div>
      {result.charge_exceeds_turnaround && (
        <div className="alert-banner" style={{ marginTop: 10 }}>
          ⚠ Charge time ({Math.round(result.ground_time_min)} min) exceeds
          turnaround target. Cycle time uses actual charge time; schedule
          density may be infeasible.
        </div>
      )}
    </div>
  )
}
