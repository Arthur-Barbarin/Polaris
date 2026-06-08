const BRANCH_COLORS = {
  capital: '#6366f1',
  revenue: '#ec4899',
  team:    '#f59e0b',
  product: '#22c55e',
}

function riskLabel(p) {
  if (p >= 0.70) return { label: 'CRITICAL', color: '#ef4444' }
  if (p >= 0.45) return { label: 'HIGH',     color: '#f59e0b' }
  if (p >= 0.20) return { label: 'MODERATE', color: '#6366f1' }
  return                 { label: 'LOW',      color: '#22c55e' }
}

// ── Resilience Index — de-emphasised reference metric ─────────
export function SurvivalScore({ resilience, mcResilience, mcRunning }) {
  const pct  = Math.round(resilience * 100)
  const risk = riskLabel(1 - resilience)

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 12,
      padding: '16px 20px',
    }}>
      {/* Label + disclaimer inline */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>
          Resilience Index
        </span>
        <span style={{
          fontSize: 9, color: '#64748b',
          padding: '1px 6px', borderRadius: 3,
          border: '1px solid #1e293b', background: '#0f1220',
        }}>
          self-reported · use for comparison
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {/* Number — smaller than before, less dominant */}
        <div style={{ fontSize: 36, fontWeight: 700, fontFamily: 'var(--mono)', color: risk.color, lineHeight: 1 }}>
          {pct}%
        </div>
        <div>
          <span style={{
            display: 'inline-block', padding: '3px 10px', borderRadius: 5,
            background: risk.color + '22', border: `1px solid ${risk.color}44`,
            color: risk.color, fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
          }}>
            {risk.label} RISK
          </span>
          <div style={{ fontSize: 10, color: '#64748b', marginTop: 6, lineHeight: 1.5 }}>
            {mcRunning ? (
              <span style={{ color: 'var(--muted)' }}>⟳ running MC…</span>
            ) : mcResilience !== undefined ? (
              <>MC mean <span style={{ fontFamily: 'var(--mono)', color: '#94a3b8', fontWeight: 600 }}>{Math.round(mcResilience * 100)}%</span> · 10k sims</>
            ) : null}
          </div>
        </div>
      </div>

      {/* Nudge toward comparison workflow */}
      <div style={{
        marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--border)',
        fontSize: 11, color: '#64748b', lineHeight: 1.5,
      }}>
        💡 Save a baseline, then adjust inputs to see how decisions shift this score.
      </div>
    </div>
  )
}

// ── Risk Decomposition ────────────────────────────────────────
export function RiskDecomposition({ decomp, branchProbs }) {
  if (!decomp) return null
  const branches = [
    { key: 'capital', label: 'Capital' },
    { key: 'revenue', label: 'Revenue' },
    { key: 'team',    label: 'Team'    },
    { key: 'product', label: 'Product' },
  ]

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 12,
      padding: '16px 20px',
    }}>
      <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: 14 }}>
        Risk Decomposition
      </div>
      {branches.map(({ key, label }) => {
        const share = decomp[key]
        const absProb = branchProbs[key]
        const color = BRANCH_COLORS[key]
        return (
          <div key={key} style={{ marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 12, color: '#cbd5e1' }}>{label}</span>
              <div style={{ display: 'flex', gap: 12 }}>
                <span style={{ fontSize: 12, color: '#64748b', fontFamily: 'var(--mono)' }}>
                  {Math.round(absProb * 100)}% fail
                </span>
                <span style={{ fontSize: 12, color, fontFamily: 'var(--mono)', fontWeight: 700, minWidth: 40, textAlign: 'right' }}>
                  {Math.round(share * 100)}%
                </span>
              </div>
            </div>
            <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${share * 100}%`,
                background: color,
                borderRadius: 3,
                transition: 'width 0.4s ease',
              }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Binding Constraint ────────────────────────────────────────
export function BindingConstraint({ constraint }) {
  if (!constraint) return null
  const color = BRANCH_COLORS[constraint.meta.branch.toLowerCase()] ?? '#6366f1'
  const pct = Math.round(constraint.prob * 100)
  const risk = riskLabel(constraint.prob)

  return (
    <div style={{
      background: 'var(--surface)',
      border: `1px solid ${color}44`,
      borderLeft: `4px solid ${color}`,
      borderRadius: 12,
      padding: '16px 20px',
    }}>
      <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: 12 }}>
        Primary Failure Mechanism
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)', marginBottom: 2 }}>
            {constraint.meta.name}
          </div>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 4,
            background: color + '22',
            color,
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: '0.08em',
          }}>
            {constraint.meta.branch}
          </span>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 28, fontWeight: 700, fontFamily: 'var(--mono)', color: risk.color, lineHeight: 1 }}>
            {pct}%
          </div>
          <div style={{ fontSize: 10, color: 'var(--muted)' }}>failure P</div>
        </div>
      </div>

      <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 12, lineHeight: 1.5, padding: '8px 12px', background: 'var(--surface2)', borderRadius: 6 }}>
        {constraint.meta.mechanism}
      </div>

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
        <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: 6 }}>
          Highest-Leverage Mitigation
        </div>
        <div style={{ fontSize: 12, color: '#e2e8f0', marginBottom: 4 }}>{constraint.meta.mitigation}</div>
        <div style={{ fontSize: 11, color: color, fontFamily: 'var(--mono)' }}>→ {constraint.meta.mitigationTarget}</div>
      </div>
    </div>
  )
}

// ── Highest-Leverage Inputs — all items highlighted by delta ──
export function SensitivityRanking({ sensitivity }) {
  if (!sensitivity || sensitivity.length === 0) return null
  const maxDelta = sensitivity[0].delta

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid #6366f144',
      borderLeft: '4px solid #6366f1',
      borderRadius: 12,
      padding: '16px 20px',
    }}>
      <div style={{ fontSize: 11, color: '#818cf8', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700, marginBottom: 4 }}>
        Highest-Leverage Inputs
      </div>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 14 }}>
        Highlighted by impact — brighter = more leverage when comparing scenarios.
      </div>

      {sensitivity.slice(0, 5).map((item, i) => {
        const ratio = item.delta / maxDelta          // 1.0 → ~0.05
        const bgAlpha  = (ratio * 0.13).toFixed(2)  // 0.13 → 0.01
        const brdAlpha = (ratio * 0.35).toFixed(2)  // 0.35 → 0.02
        const barAlpha = (0.30 + ratio * 0.70).toFixed(2) // bright → dim
        const textColor = '#e2e8f0'  // all levers white — rank/brightness already shown by bg opacity
        const deltaColor = i === 0 ? '#818cf8' : i === 1 ? '#6366f1' : '#4f46e5'

        return (
          <div key={item.key} style={{
            padding: i === 0 ? '11px 13px' : '8px 11px',
            borderRadius: 8,
            marginBottom: i < 4 ? 8 : 0,
            background: `rgba(99,102,241,${bgAlpha})`,
            border: `1px solid rgba(99,102,241,${brdAlpha})`,
            transition: 'background 0.3s',
          }}>
            {i === 0 && (
              <div style={{ fontSize: 9, color: '#818cf8', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 5 }}>
                #1 lever — highest impact
              </div>
            )}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                <span style={{
                  width: 17, height: 17, borderRadius: 4, flexShrink: 0,
                  background: `rgba(99,102,241,${(ratio * 0.25).toFixed(2)})`,
                  border: `1px solid rgba(99,102,241,${brdAlpha})`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 9, fontWeight: 700, color: i === 0 ? '#818cf8' : '#6366f1',
                }}>
                  {i + 1}
                </span>
                <span style={{ fontSize: i === 0 ? 13 : 12, fontWeight: i === 0 ? 600 : 400, color: textColor }}>
                  {item.label}
                </span>
              </div>
              <span style={{ fontSize: i === 0 ? 13 : 11, fontFamily: 'var(--mono)', fontWeight: i < 2 ? 700 : 500, color: deltaColor }}>
                Δ{(item.delta * 100).toFixed(1)}pp
              </span>
            </div>
            <div style={{ height: i === 0 ? 5 : 3, background: '#1e293b', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${ratio * 100}%`,
                background: `rgba(99,102,241,${barAlpha})`,
                borderRadius: 3,
                transition: 'width 0.4s ease',
              }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}
