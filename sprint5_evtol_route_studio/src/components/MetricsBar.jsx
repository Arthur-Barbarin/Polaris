import { fmt_usd, fmt_pct, fmt_num } from '../models/economics.js'

function Metric({ label, value, sub, color = 'neutral', context }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className={`metric-value metric-${color}`}>{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
      {context && (
        <div style={{
          marginTop: 6, paddingTop: 6, borderTop: '1px solid #1e2535',
          fontSize: 10, color: '#3a4060', lineHeight: 1.4,
        }}>
          {context}
        </div>
      )}
    </div>
  )
}

export default function MetricsBar({ result }) {
  const { annual_profit, casm, breakeven_load_factor, payback_years,
    flights_per_day, annual_flights, annual_flights_revenue, breakeven_fare_per_seat,
    annual_margin_pct, deadhead_factor, load_factor } = result

  const profitColor = annual_profit > 0 ? 'positive' : annual_profit > -200_000 ? 'warn' : 'negative'
  const beColor = breakeven_load_factor < 0.70 ? 'positive' : breakeven_load_factor < 0.90 ? 'warn' : 'negative'
  const paybackColor = payback_years < 8 ? 'positive' : payback_years < 15 ? 'warn' : 'negative'

  // CASM context: describe it in plain terms
  const casmContext = casm < 0.5 ? 'Very competitive — below turboprop range'
    : casm < 1.0 ? 'Competitive — below helicopter, above regional jet'
    : casm < 4.2 ? 'Moderate — cheaper than helicopter charter'
    : 'High — exceeds helicopter charter costs'

  return (
    <div className="metrics-grid">
      <Metric
        label="Annual profit / aircraft"
        value={fmt_usd(annual_profit)}
        sub={`${fmt_pct(annual_margin_pct)} margin · ${Math.round(annual_flights_revenue).toLocaleString()} rev. flights`}
        color={profitColor}
      />
      <Metric
        label="Break-even load factor"
        value={isFinite(breakeven_load_factor) ? fmt_pct(breakeven_load_factor) : '∞'}
        sub={`Current: ${fmt_pct(load_factor)} · Min fare: ${fmt_usd(breakeven_fare_per_seat)}/seat`}
        color={beColor}
        context="Industry target: 60–75% sustained LF for UAM viability"
      />
      <Metric
        label="CASM"
        value={`$${casm.toFixed(2)}/ASM`}
        sub="cost per available seat-mile"
        color="neutral"
        context={casmContext}
      />
      <Metric
        label="Payback period"
        value={isFinite(payback_years) ? `${fmt_num(payback_years, 1)} yr` : '∞'}
        sub={`${flights_per_day}/day realised · ${result.flights_per_day_capacity ?? flights_per_day}/day capacity`}
        color={paybackColor}
        context={`Slot capacity filled at ${Math.round((result.demand_utilization_pct ?? 1) * 100)}% demand. Recovering capex from net operating margin.`}
      />
    </div>
  )
}
