const BRANCH_COLORS = {
  capital: '#6366f1',
  revenue: '#ec4899',
  team:    '#f59e0b',
  product: '#22c55e',
}

function delta(current, baseline, invert = false) {
  const d = current - baseline
  const pp = Math.round(d * 100)
  // For resilience: positive = good. For branch failure: negative = good.
  const isGood = invert ? pp < 0 : pp > 0
  const isNeutral = pp === 0
  return {
    pp,
    label: pp === 0 ? '—' : `${pp > 0 ? '+' : ''}${pp}pp`,
    color: isNeutral ? '#475569' : isGood ? '#22c55e' : '#ef4444',
    arrow: isNeutral ? '' : pp > 0 ? ' ▲' : ' ▼',
  }
}

function fmtVal(key, val) {
  if (key === 'cash_on_hand') return '$' + (val >= 1e6 ? (val/1e6).toFixed(2)+'M' : Math.round(val/1000)+'k')
  if (key === 'monthly_burn') return '$' + Math.round(val/1000)+'k'
  if (key === 'monthly_retention') return (val*100).toFixed(1)+'%'
  if (key === 'monthly_growth_rate') return (val*100).toFixed(1)+'%'
  if (key === 'largest_customer_pct') return (val*100).toFixed(0)+'%'
  if (key === 'fundraising_timeline') return val+' mo'
  if (['fundraise_confidence','investor_traction','key_person_dependency',
       'hiring_difficulty','technical_complexity','customer_validation'].includes(key))
    return '★'.repeat(val) + '☆'.repeat(5-val)
  return val
}

const INPUT_LABELS = {
  cash_on_hand:          'Cash on Hand',
  monthly_burn:          'Monthly Burn',
  fundraising_timeline:  'Fundraising Timeline',
  fundraise_confidence:  'Fundraise Confidence',
  investor_traction:     'Investor Traction',
  monthly_retention:     'Monthly Retention',
  monthly_growth_rate:   'Monthly Growth Rate',
  largest_customer_pct:  'Customer Concentration',
  key_person_dependency: 'Key Person Dependency',
  hiring_difficulty:     'Hiring Difficulty',
  technical_complexity:  'Technical Complexity',
  customer_validation:   'Customer Validation',
}

export default function ScenarioComparison({ baseline, current }) {
  // ── Empty state — no baseline saved yet ──────────────────────
  if (!baseline) {
    return (
      <div style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderLeft: '4px solid #334155',
        borderRadius: 12,
        padding: '20px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 24,
        flexWrap: 'wrap',
      }}>
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#64748b', marginBottom: 8 }}>
            Scenario Comparison
          </div>
          <div style={{ fontSize: 14, color: '#94a3b8', lineHeight: 1.6 }}>
            Save a baseline to compare two strategic scenarios side-by-side.
          </div>
          <div style={{ fontSize: 12, color: '#64748b', marginTop: 6 }}>
            Resilience delta · Branch-level risk shifts · Changed inputs
          </div>
        </div>
        <div style={{
          padding: '10px 18px', borderRadius: 8,
          background: '#6366f111', border: '1px solid #6366f133',
          fontSize: 12, color: '#818cf8', fontWeight: 600,
        }}>
          ⊕ Save Baseline in the sidebar to get started
        </div>
      </div>
    )
  }

  // ── Comparison state ─────────────────────────────────────────
  const { inputs: bInputs, resilience: bRes, branchProbs: bBranch } = baseline
  const { inputs: cInputs, resilience: cRes, branchProbs: cBranch } = current

  const resD = delta(cRes, bRes, false)  // higher resilience = good

  const branches = ['capital', 'revenue', 'team', 'product']

  // Find changed inputs
  const changedInputs = Object.keys(INPUT_LABELS).filter(k => {
    const a = bInputs[k], b = cInputs[k]
    if (a === undefined || b === undefined) return false
    if (typeof a === 'number') return Math.abs(a - b) > 0.0001
    return a !== b
  })

  return (
    <div style={{
      background: 'var(--surface)',
      border: `1px solid ${resD.pp === 0 ? 'var(--border)' : resD.pp > 0 ? '#22c55e44' : '#ef444444'}`,
      borderLeft: `4px solid ${resD.pp === 0 ? 'var(--border)' : resD.pp > 0 ? '#22c55e' : '#ef4444'}`,
      borderRadius: 12,
      padding: '16px 20px',
    }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
            color: 'var(--muted)',
          }}>
            Scenario Comparison
          </span>
          <span style={{ fontSize: 11, color: '#64748b' }}>Baseline → Current</span>
        </div>
        {changedInputs.length > 0 && (
          <span style={{ fontSize: 11, color: '#475569' }}>
            {changedInputs.length} input{changedInputs.length > 1 ? 's' : ''} changed
          </span>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>

        {/* Left: Resilience + branches */}
        <div>
          {/* Resilience headline */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '10px 14px',
            background: 'var(--surface2)',
            borderRadius: 8,
            marginBottom: 12,
          }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 3 }}>Resilience Index</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 22, fontWeight: 700, color: '#64748b' }}>
                  {Math.round(bRes * 100)}%
                </span>
                <span style={{ color: '#475569', fontSize: 13 }}>→</span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 22, fontWeight: 700, color: 'var(--text)' }}>
                  {Math.round(cRes * 100)}%
                </span>
                <span style={{
                  fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 700,
                  color: resD.color, marginLeft: 4,
                }}>
                  {resD.label}{resD.arrow}
                </span>
              </div>
            </div>
          </div>

          {/* Branch deltas */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {branches.map(b => {
              const bProb = bBranch[b], cProb = cBranch[b]
              const d = delta(cProb, bProb, true)  // lower failure = good
              const color = BRANCH_COLORS[b]
              return (
                <div key={b} style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '6px 10px', borderRadius: 6,
                  background: d.pp === 0 ? 'transparent' : d.color + '0f',
                  border: `1px solid ${d.pp === 0 ? 'var(--border)' : d.color + '33'}`,
                }}>
                  <span style={{
                    width: 8, height: 8, borderRadius: 2,
                    background: color, flexShrink: 0, display: 'inline-block',
                  }} />
                  <span style={{ fontSize: 12, color: '#94a3b8', flex: 1, textTransform: 'capitalize' }}>{b}</span>
                  <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: '#475569' }}>
                    {Math.round(bProb * 100)}%
                  </span>
                  <span style={{ fontSize: 11, color: '#64748b' }}>→</span>
                  <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: '#94a3b8' }}>
                    {Math.round(cProb * 100)}%
                  </span>
                  <span style={{
                    fontSize: 11, fontFamily: 'var(--mono)', fontWeight: 700,
                    color: d.color, minWidth: 44, textAlign: 'right',
                  }}>
                    {d.label}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right: Changed inputs */}
        <div>
          <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>
            Changed Inputs
          </div>
          {changedInputs.length === 0 ? (
            <div style={{ fontSize: 12, color: '#64748b', fontStyle: 'italic' }}>
              No inputs changed from baseline.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {changedInputs.map(k => {
                const from = bInputs[k], to = cInputs[k]
                // Direction: is "to" better or worse?
                const worseBigger = ['monthly_burn','fundraising_timeline','largest_customer_pct',
                                     'key_person_dependency','hiring_difficulty','technical_complexity']
                const worseSmaller = ['cash_on_hand','monthly_retention','monthly_growth_rate',
                                      'fundraise_confidence','investor_traction','customer_validation']
                let improved = null
                if (worseBigger.includes(k)) improved = to < from
                if (worseSmaller.includes(k)) improved = to > from

                return (
                  <div key={k} style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '5px 10px', borderRadius: 6,
                    background: improved === null ? 'var(--surface2)' : improved ? '#22c55e0d' : '#ef44440d',
                    border: `1px solid ${improved === null ? 'var(--border)' : improved ? '#22c55e33' : '#ef444433'}`,
                  }}>
                    <span style={{
                      width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                      background: improved === null ? '#475569' : improved ? '#22c55e' : '#ef4444',
                      display: 'inline-block',
                    }} />
                    <span style={{ fontSize: 11, color: '#64748b', flex: 1 }}>
                      {INPUT_LABELS[k]}
                    </span>
                    <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: '#475569' }}>
                      {fmtVal(k, from)}
                    </span>
                    <span style={{ fontSize: 11, color: '#64748b' }}>→</span>
                    <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text)', fontWeight: 600 }}>
                      {fmtVal(k, to)}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
