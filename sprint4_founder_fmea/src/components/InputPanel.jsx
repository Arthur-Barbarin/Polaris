const BRANCH_COLORS = {
  Capital: '#6366f1',
  Revenue: '#ec4899',
  Team:    '#f59e0b',
  Product: '#22c55e',
}

function fmt(val, type) {
  if (type === 'currency') return '$' + (val >= 1e6 ? (val/1e6).toFixed(2)+'M' : val >= 1000 ? Math.round(val/1000)+'k' : val)
  if (type === 'pct') return (val * 100).toFixed(1) + '%'
  if (type === 'months') return val + ' mo'
  if (type === 'stars') return '★'.repeat(val) + '☆'.repeat(5 - val)
  return val
}

function Slider({ label, value, min, max, step, type, onChange, hint }) {
  const pct = ((value - min) / (max - min)) * 100
  const trackStyle = {
    background: `linear-gradient(to right, var(--accent2) ${pct}%, var(--border) ${pct}%)`
  }
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
        <span style={{ fontSize: 12, color: '#cbd5e1' }}>{label}</span>
        <span style={{ fontSize: 12, color: 'var(--text)', fontFamily: 'var(--mono)', fontWeight: 600 }}>
          {fmt(value, type)}
        </span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        style={trackStyle}
        onChange={e => onChange(type === 'pct' ? parseFloat(e.target.value) : parseFloat(e.target.value))}
      />
      {hint && <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 3 }}>{hint}</div>}
    </div>
  )
}

function Section({ title, color, children }) {
  return (
    <div style={{
      background: 'var(--surface2)',
      border: `1px solid ${color}33`,
      borderLeft: `3px solid ${color}`,
      borderRadius: 8,
      padding: '14px 16px',
      marginBottom: 12,
    }}>
      <div style={{
        fontSize: 10, fontWeight: 700, letterSpacing: '0.1em',
        textTransform: 'uppercase', color, marginBottom: 14,
      }}>
        {title}
      </div>
      {children}
    </div>
  )
}

export default function InputPanel({ inputs, onChange }) {
  const set = (key) => (val) => onChange({ ...inputs, [key]: val })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      <Section title="Capital" color={BRANCH_COLORS.Capital}>
        <Slider label="Cash on Hand" value={inputs.cash_on_hand}
          min={100000} max={10000000} step={50000} type="currency" onChange={set('cash_on_hand')} />
        <Slider label="Monthly Burn (Gross)" value={inputs.monthly_burn}
          min={10000} max={1000000} step={5000} type="currency" onChange={set('monthly_burn')}
          hint={(() => {
            const nb = inputs.monthly_burn - (inputs.current_mrr || 0)
            return nb <= 0
              ? `Profitable — MRR covers burn`
              : `Net burn: ${fmt(nb, 'currency')}/mo · Runway: ${(inputs.cash_on_hand / nb).toFixed(1)} months`
          })()} />
        <Slider label="Current MRR" value={inputs.current_mrr || 0}
          min={0} max={500000} step={5000} type="currency" onChange={set('current_mrr')}
          hint="Monthly recurring revenue — offsets burn & grows with growth rate" />
        <Slider label="Fundraising Timeline" value={inputs.fundraising_timeline}
          min={3} max={24} step={1} type="months" onChange={set('fundraising_timeline')} />
        <Slider label="Fundraise Confidence" value={inputs.fundraise_confidence}
          min={1} max={5} step={1} type="stars" onChange={set('fundraise_confidence')}
          hint="1 = very uncertain, 5 = strong conviction" />
        <Slider label="Investor Traction" value={inputs.investor_traction}
          min={1} max={5} step={1} type="stars" onChange={set('investor_traction')}
          hint="1 = no investor interest, 5 = soft commits in hand" />
      </Section>

      <Section title="Revenue" color={BRANCH_COLORS.Revenue}>
        <Slider label="Monthly Retention" value={inputs.monthly_retention}
          min={0.80} max={0.999} step={0.001} type="pct" onChange={set('monthly_retention')}
          hint={`Annual NRR ≈ ${(Math.pow(inputs.monthly_retention, 12) * 100).toFixed(1)}%  · floor: >80%, ideal: >90%`} />
        <Slider label="Monthly Growth Rate" value={inputs.monthly_growth_rate}
          min={0} max={0.30} step={0.005} type="pct" onChange={set('monthly_growth_rate')}
          hint="Series A benchmark: ≥8% MoM" />
        <Slider label="Largest Customer %" value={inputs.largest_customer_pct}
          min={0.01} max={0.99} step={0.01} type="pct" onChange={set('largest_customer_pct')}
          hint="% of MRR from single customer" />
      </Section>

      <Section title="Team" color={BRANCH_COLORS.Team}>
        <Slider label="Key Person Dependency" value={inputs.key_person_dependency}
          min={1} max={5} step={1} type="stars" onChange={set('key_person_dependency')}
          hint="1 = distributed knowledge, 5 = single critical person holds everything" />
        <Slider label="Hiring Difficulty" value={inputs.hiring_difficulty}
          min={1} max={5} step={1} type="stars" onChange={set('hiring_difficulty')}
          hint="1 = easy market, 5 = extremely competitive" />
      </Section>

      <Section title="Product" color={BRANCH_COLORS.Product}>
        <Slider label="Technical Complexity" value={inputs.technical_complexity}
          min={1} max={5} step={1} type="stars" onChange={set('technical_complexity')}
          hint="1 = proven stack, 5 = frontier/unvalidated" />
        <Slider label="Customer Validation" value={inputs.customer_validation}
          min={1} max={5} step={1} type="stars" onChange={set('customer_validation')}
          hint="1 = idea stage, 5 = strong NPS + expansion revenue" />
      </Section>
    </div>
  )
}
