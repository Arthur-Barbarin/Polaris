/**
 * P&L breakdown — replaces the floating waterfall.
 * Horizontal bars sorted by size, with Revenue and Net as bookends.
 * Much more readable than a floating waterfall in Recharts without custom SVG connectors.
 */

const fmt = (v) => {
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  return `$${Math.round(v / 1000)}k`;
};

export default function WaterfallChart({ result }) {
  const af = result.annual_flights;

  // Cost items sorted by size descending
  const costs = [
    { name: 'Maintenance', value: result.maintenance_cost * af, type: 'cost' },
    { name: 'Landing fees', value: result.landing_fee * af, type: 'cost' },
    { name: 'Capex (annl.)', value: result.annual_capex, type: 'capex' },
    { name: 'Crew', value: result.crew_cost * af, type: 'cost' },
    { name: 'Energy', value: result.energy_cost * af, type: 'cost' },
  ].sort((a, b) => b.value - a.value);

  const revenue = result.annual_revenue;
  const profit = result.annual_profit;
  const isProfitable = profit >= 0;

  const COLORS = {
    revenue: '#2DBD7E',
    cost: '#E85C5C',
    capex: '#E8813A',
    profit: '#2DBD7E',
    loss: '#E85C5C',
  };

  const Row = ({ name, value, type, isSpecial }) => {
    const color = COLORS[type];
    const pct = Math.min(value / revenue, 1);
    const pctLabel = ((value / revenue) * 100).toFixed(0) + '%';

    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: isSpecial ? 0 : 7 }}>
        {/* Label */}
        <div style={{
          width: 94, fontSize: 11, flexShrink: 0, textAlign: 'right',
          color: isSpecial ? '#c8d0e8' : '#7a8099',
          fontWeight: isSpecial ? 600 : 400,
        }}>
          {name}
        </div>

        {/* Bar */}
        <div style={{ flex: 1, height: isSpecial ? 18 : 13, background: '#0a0d14', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{
            width: `${pct * 100}%`,
            height: '100%',
            background: color,
            opacity: isSpecial ? 0.9 : 0.65,
            borderRadius: 3,
            transition: 'width 0.3s ease',
          }} />
        </div>

        {/* Value */}
        <div style={{
          width: 62, fontSize: 11, flexShrink: 0,
          color, fontWeight: isSpecial ? 700 : 500,
        }}>
          {isSpecial ? fmt(value) : fmt(value)}
        </div>

        {/* % of revenue */}
        <div style={{ width: 32, fontSize: 10, color: '#3a4060', textAlign: 'right', flexShrink: 0 }}>
          {isSpecial ? '' : pctLabel}
        </div>
      </div>
    );
  };

  const Sep = () => (
    <div style={{ borderTop: '1px solid #252d40', margin: '10px 0 10px 104px' }} />
  );

  return (
    <div className="panel">
      <div className="chart-title">Annual P&L breakdown / aircraft</div>
      <div className="chart-sub">Revenue → cost items (sorted by size) → net profit</div>

      <div style={{ marginTop: 4 }}>
        <Row name="Revenue" value={revenue} type="revenue" isSpecial />

        <Sep />

        {costs.map(item => (
          <Row key={item.name} name={item.name} value={item.value} type={item.type} />
        ))}

        <Sep />

        <Row
          name={isProfitable ? 'Net profit' : 'Net loss'}
          value={Math.abs(profit)}
          type={isProfitable ? 'profit' : 'loss'}
          isSpecial
        />
      </div>

      {/* Margin callout */}
      <div style={{
        marginTop: 14, padding: '8px 12px',
        background: isProfitable ? '#0d2a1a' : '#2a0d0d',
        border: `1px solid ${isProfitable ? '#2DBD7E33' : '#E85C5C33'}`,
        borderRadius: 6,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span style={{ fontSize: 11, color: '#5a6080' }}>
          {result.annual_flights_revenue.toLocaleString()} revenue flights · {result.annual_flights.toLocaleString()} total (incl. deadhead)
        </span>
        <span style={{ fontSize: 12, fontWeight: 700, color: isProfitable ? '#2DBD7E' : '#E85C5C' }}>
          {isProfitable ? '+' : ''}{(result.annual_margin_pct * 100).toFixed(1)}% margin
        </span>
      </div>

      <div className="source-line">Opex applied to all flights incl. deadhead. Capex = straight-line depreciation + infra share.</div>
    </div>
  );
}
