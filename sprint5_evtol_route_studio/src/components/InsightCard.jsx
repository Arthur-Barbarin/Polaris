const SEVERITY_STYLES = {
  ok:       { bg: '#0d2a1a', border: '#2DBD7E', icon: '✓', iconColor: '#2DBD7E', labelColor: '#2DBD7E' },
  medium:   { bg: '#1a1a0a', border: '#C8AA2D', icon: '◈', iconColor: '#C8AA2D', labelColor: '#C8AA2D' },
  high:     { bg: '#2a1a0a', border: '#E8813A', icon: '⚠', iconColor: '#E8813A', labelColor: '#E8813A' },
  critical: { bg: '#2a0d0d', border: '#E85C5C', icon: '✗', iconColor: '#E85C5C', labelColor: '#E85C5C' },
};

export default function InsightCard({ constraint, result }) {
  const s = SEVERITY_STYLES[constraint.severity] || SEVERITY_STYLES.medium;

  return (
    <div style={{
      background: s.bg,
      border: `1px solid ${s.border}`,
      borderRadius: 10,
      padding: '16px 20px',
      display: 'grid',
      gridTemplateColumns: 'auto 1fr auto',
      gap: '0 16px',
      alignItems: 'start',
    }}>
      {/* Icon */}
      <div style={{
        fontSize: 22,
        color: s.iconColor,
        fontWeight: 700,
        lineHeight: 1.2,
        paddingTop: 2,
      }}>
        {s.icon}
      </div>

      {/* Main content */}
      <div>
        <div style={{
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: '0.5px',
          textTransform: 'uppercase',
          color: s.labelColor,
          marginBottom: 4,
        }}>
          Binding constraint — {constraint.label}
        </div>
        <div style={{ fontSize: 13, color: '#c8d0e8', lineHeight: 1.55, marginBottom: 8 }}>
          {constraint.detail}
        </div>
        <div style={{
          fontSize: 12,
          color: '#7a8099',
          display: 'flex',
          alignItems: 'baseline',
          gap: 6,
        }}>
          <span style={{ color: '#4A90D9', fontWeight: 600, flexShrink: 0 }}>Lever →</span>
          {constraint.lever}
        </div>
      </div>

      {/* Side metrics */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        minWidth: 110,
        textAlign: 'right',
      }}>
        <div>
          <div style={{ fontSize: 10, color: '#3a4060', textTransform: 'uppercase', letterSpacing: '0.5px' }}>B/E load factor</div>
          <div style={{
            fontSize: 18,
            fontWeight: 700,
            color: result.breakeven_load_factor < 0.70 ? '#2DBD7E'
              : result.breakeven_load_factor < 0.90 ? '#E8813A' : '#E85C5C',
          }}>
            {isFinite(result.breakeven_load_factor) ? (result.breakeven_load_factor * 100).toFixed(1) + '%' : '∞'}
          </div>
          <div style={{ fontSize: 10, color: '#5a6080' }}>current: {(result.load_factor * 100).toFixed(0)}%</div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: '#3a4060', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Min viable fare</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#c8d0e8' }}>
            ${result.breakeven_fare_per_seat.toFixed(0)}<span style={{ fontSize: 11, fontWeight: 400, color: '#5a6080' }}>/seat</span>
          </div>
        </div>
      </div>
    </div>
  );
}
