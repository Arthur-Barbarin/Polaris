import logo from './assets/Polaris_logo.png'
import { useMemo, useState } from 'react'
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  Cell,
} from 'recharts'

// ── Input metadata ──────────────────────────────────────────────────────────
// Provides frontend context for each input slider.
const INPUT_META = {
  saf_share: {
    label: 'SAF share',
    unit: '%',
    hint: '% of fuel mix that is Sustainable Aviation Fuel. 0 = pure kerosene, 100 = full SAF.',
    min: 0,
    max: 100,
    step: 1,
  },
  hydrogen_readiness: {
    label: 'Hydrogen readiness',
    unit: 'index (0–100)',
    hint: 'Heuristic technology maturity signal. 0 = no hydrogen pathway, 100 = fully deployment-ready.',
    min: 0,
    max: 100,
    step: 1,
  },
  electricity_price: {
    label: 'Electricity price exposure',
    unit: 'index (0–100)',
    hint: 'Relative electricity cost sensitivity. 0 = no exposure, 100 = high-cost grid dependency.',
    min: 0,
    max: 100,
    step: 1,
  },
  carbon_price: {
    label: 'Carbon price signal',
    unit: '$/tCO₂ (0–200)',
    hint: 'Policy carbon price assumption. 0 = no carbon cost, 200 = strong policy environment.',
    min: 0,
    max: 200,
    step: 5,
  },
  demand_growth: {
    label: 'Demand growth signal',
    unit: 'index (0–100)',
    hint: 'Relative market demand growth signal. 0 = stagnant market, 100 = fast-growing market.',
    min: 0,
    max: 100,
    step: 1,
  },
}

// ── Color helpers ───────────────────────────────────────────────────────────
function readingColor(reading) {
  if (reading === 'Better than benchmark') return { bg: '#dcfce7', text: '#166534', bar: '#22c55e' }
  if (reading === 'Near benchmark') return { bg: '#fef3c7', text: '#92400e', bar: '#f59e0b' }
  return { bg: '#fee2e2', text: '#991b1b', bar: '#ef4444' }
}

function readingPillStyle(reading) {
  const c = readingColor(reading)
  return {
    display: 'inline-block',
    padding: '5px 10px',
    borderRadius: '999px',
    fontSize: '12px',
    fontWeight: '700',
    background: c.bg,
    color: c.text,
    whiteSpace: 'nowrap',
  }
}

// ── Custom tooltip for bar chart ────────────────────────────────────────────
function BenchmarkTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null
  const d = payload[0].payload
  return (
    <div style={{
      background: 'white',
      border: '1px solid #e2e8f0',
      borderRadius: '12px',
      padding: '12px 16px',
      fontSize: '13px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.1)',
      maxWidth: '240px',
    }}>
      <div style={{ fontWeight: '700', marginBottom: '6px', color: '#0f172a' }}>{d.name}</div>
      <div style={{ color: '#475569' }}>Scenario: <strong>{d.scenario}</strong></div>
      <div style={{ color: '#475569' }}>Benchmark: <strong>{d.benchmark}</strong></div>
      <div style={{ marginTop: '6px' }}>
        <span style={readingPillStyle(d.reading)}>{d.reading}</span>
      </div>
    </div>
  )
}

// ── Main App ────────────────────────────────────────────────────────────────
export default function App() {
  const [concept, setConcept] = useState('narrowbody')
  const [safShare, setSafShare] = useState(35)
  const [hydrogenReadiness, setHydrogenReadiness] = useState(42)
  const [electricityPrice, setElectricityPrice] = useState(18)
  const [carbonPrice, setCarbonPrice] = useState(75)
  const [demandGrowth, setDemandGrowth] = useState(22)

  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function runScenario() {
    setLoading(true)
    setError('')
    try {
      const response = await fetch('http://127.0.0.1:8000/run-scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          concept,
          saf_share: Number(safShare),
          hydrogen_readiness: Number(hydrogenReadiness),
          electricity_price: Number(electricityPrice),
          carbon_price: Number(carbonPrice),
          demand_growth: Number(demandGrowth),
        }),
      })
      if (!response.ok) throw new Error('Backend error')
      const data = await response.json()
      setResult(data)
    } catch {
      setError('Unable to reach the backend. Make sure FastAPI is running on port 8000.')
    } finally {
      setLoading(false)
    }
  }

  // Radar chart: all axes point outward = better. Inversions are explicit.
  const radarData = useMemo(() => {
    if (!result) return []
    const o = result.outputs
    return [
      { metric: 'Cost position', value: Math.max(0, Math.min(100, 200 - o.cost_pressure_index)), note: '↑ lower cost pressure' },
      { metric: 'Adoption', value: o.adoption_index, note: '↑ higher is better' },
      { metric: 'Climate', value: Math.max(0, Math.min(100, 100 - o.emissions_index)), note: '↑ lower emissions' },
      { metric: 'Readiness', value: Math.max(0, Math.min(100, 100 - o.technical_risk_index)), note: '↑ lower risk' },
      { metric: 'Narrative', value: o.narrative_index, note: '↑ stronger narrative (heuristic)' },
    ]
  }, [result])

  // Benchmark comparison bar chart: scenario value vs benchmark value per metric
  const barData = useMemo(() => {
    if (!result) return []
    return result.comparison_table.map((row) => ({
      name: row.metric_label.replace(' index', '').replace(' ⚠', ' ⚠'),
      scenario: row.scenario_value,
      benchmark: row.benchmark_value,
      reading: row.reading,
      lower_is_better: row.lower_is_better,
    }))
  }, [result])

  return (
    <div style={styles.page}>
      <div style={styles.container}>

        {/* Disclaimer banner */}
        <div style={styles.disclaimer}>
          <span style={styles.disclaimerBadge}>Prototype</span>
          This tool is a decision-support prototype — not a certified engineering or financial model.
          All metrics are heuristic indexes. Benchmarks are illustrative references, not official standards.
          Use for structured conversation and early-stage exploration only.
        </div>

        <div style={styles.topBar}>
          <img src={logo} alt="Polaris logo" style={styles.logoCentered} />
        </div>

        <div style={styles.hero}>
          <h1 style={styles.title}>Scenario Explorer</h1>
          <p style={styles.subtitle}>
            Test a set of assumptions and compare the resulting implications against explicit reference benchmarks.
          </p>
        </div>

        <div style={styles.grid}>

          {/* ── Left column: inputs ── */}
          <div style={styles.leftColumn}>
            <div style={styles.card}>
              <div style={styles.sectionHeader}>
                <div style={styles.sectionEyebrow}>Inputs</div>
                <h2 style={styles.sectionTitle}>Scenario controls</h2>
              </div>

              <label style={styles.label}>Concept</label>
              <select value={concept} onChange={(e) => setConcept(e.target.value)} style={styles.input}>
                <option value="regional">Regional aircraft</option>
                <option value="narrowbody">Low-emission narrowbody</option>
                <option value="drone">Advanced air mobility / drone</option>
              </select>

              {[
                { key: 'saf_share', state: safShare, setter: setSafShare },
                { key: 'hydrogen_readiness', state: hydrogenReadiness, setter: setHydrogenReadiness },
                { key: 'electricity_price', state: electricityPrice, setter: setElectricityPrice },
                { key: 'carbon_price', state: carbonPrice, setter: setCarbonPrice },
                { key: 'demand_growth', state: demandGrowth, setter: setDemandGrowth },
              ].map(({ key, state, setter }) => {
                const meta = INPUT_META[key]
                return (
                  <div key={key}>
                    <label style={styles.label}>
                      {meta.label}
                      <span style={styles.unitBadge}>{meta.unit}</span>
                    </label>
                    <input
                      type="number"
                      value={state}
                      min={meta.min}
                      max={meta.max}
                      step={meta.step}
                      onChange={(e) => setter(e.target.value)}
                      style={styles.input}
                    />
                    <p style={styles.inputHint}>{meta.hint}</p>
                  </div>
                )
              })}

              <button onClick={runScenario} disabled={loading} style={styles.button}>
                {loading ? 'Running…' : 'Run scenario'}
              </button>

              {error && <p style={styles.error}>{error}</p>}
            </div>

            <div style={styles.darkCard}>
              <div style={styles.darkEyebrow}>Design principle</div>
              <div style={styles.darkTitle}>Structured assumptions, not black-box scoring</div>
              <p style={styles.darkText}>
                Polaris shows what your assumptions <em>imply</em> relative to explicit reference points —
                not a magic score. Every number is a proxy. Every benchmark is a reference, not a truth.
              </p>
            </div>
          </div>

          {/* ── Right column: results ── */}
          <div style={styles.rightColumn}>

            {/* Headline */}
            <div style={styles.heroResultCard}>
              <div>
                <div style={styles.sectionEyebrow}>Scenario implications</div>
                <h2 style={styles.resultHeadline}>
                  {result ? result.headline : 'Run a scenario to see benchmarked implications'}
                </h2>
                <p style={styles.resultSubtext}>
                  {result
                    ? result.interpretation
                    : 'The goal is not to produce a magic score, but to show what your assumptions imply relative to explicit reference points.'}
                </p>
              </div>
            </div>

            {/* KPI cards — 4 core metrics only */}
            <div style={styles.kpiGrid}>
              <KpiCard
                title="Cost pressure index"
                value={result ? result.outputs.cost_pressure_index : '--'}
                subtitle="Lower = more favorable cost position"
                benchmark="Ref: 100"
                reading={result ? result.comparison_table.find(r => r.key === 'cost_pressure_index')?.reading : null}
              />
              <KpiCard
                title="Emissions intensity index"
                value={result ? result.outputs.emissions_index : '--'}
                subtitle="Lower = better climate performance"
                benchmark="CORSIA proxy: 80"
                reading={result ? result.comparison_table.find(r => r.key === 'emissions_index')?.reading : null}
              />
              <KpiCard
                title="Technical readiness risk"
                value={result ? result.outputs.technical_risk_index : '--'}
                subtitle="Lower = closer to deployment-ready"
                benchmark="Threshold proxy: 30"
                reading={result ? result.comparison_table.find(r => r.key === 'technical_risk_index')?.reading : null}
              />
              <KpiCard
                title="Adoption potential index"
                value={result ? result.outputs.adoption_index : '--'}
                subtitle="Higher = stronger market traction signal"
                benchmark="Traction ref: 50"
                reading={result ? result.comparison_table.find(r => r.key === 'adoption_index')?.reading : null}
              />
            </div>

            {/* Narrative index — shown separately with caveat */}
            {result && (
              <div style={styles.narrativeCard}>
                <div style={styles.narrativeLeft}>
                  <div style={styles.sectionEyebrow}>Heuristic signal</div>
                  <div style={styles.narrativeTitle}>Narrative strength index</div>
                  <p style={styles.narrativeNote}>
                    ⚠ Heuristic composite only — not a predictive metric. Use for investor framing conversations, not as a forecast.
                    Benchmark reference: 65.
                  </p>
                </div>
                <div style={styles.narrativeRight}>
                  <div style={styles.narrativeValue}>{result.outputs.narrative_index}</div>
                  <span style={readingPillStyle(result.comparison_table.find(r => r.key === 'narrative_index')?.reading)}>
                    {result.comparison_table.find(r => r.key === 'narrative_index')?.reading}
                  </span>
                </div>
              </div>
            )}

            {/* Charts */}
            <div style={styles.chartGrid}>

              {/* Radar chart */}
              <div style={styles.card}>
                <div style={styles.chartHeader}>
                  <div style={styles.sectionEyebrow}>Balanced view</div>
                  <h3 style={styles.chartTitle}>Scenario profile</h3>
                  <p style={styles.chartNote}>All axes: outward = more favorable. "Cost position" and "Climate" are inverted so higher = better.</p>
                </div>
                <div style={styles.chartBox}>
                  {result ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart data={radarData}>
                        <PolarGrid />
                        <PolarAngleAxis dataKey="metric" tick={{ fontSize: 12 }} />
                        <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                        <Radar dataKey="value" stroke="#0f172a" fill="#0f172a" fillOpacity={0.3} />
                      </RadarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={styles.chartPlaceholder}>Run a scenario to generate the radar chart.</div>
                  )}
                </div>
              </div>

              {/* Benchmark bar chart — replaces the single-point scatter */}
              <div style={styles.card}>
                <div style={styles.chartHeader}>
                  <div style={styles.sectionEyebrow}>Trade-off view</div>
                  <h3 style={styles.chartTitle}>Scenario vs benchmarks</h3>
                  <p style={styles.chartNote}>Colored bars = your scenario. Grey line = benchmark reference. Colors reflect benchmark reading.</p>
                </div>
                <div style={styles.chartBox}>
                  {result ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={barData}
                        layout="vertical"
                        margin={{ top: 8, right: 28, bottom: 8, left: 8 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                        <XAxis type="number" domain={[0, 120]} tick={{ fontSize: 11 }} />
                        <YAxis
                          type="category"
                          dataKey="name"
                          width={100}
                          tick={{ fontSize: 10 }}
                          tickFormatter={(v) => v.length > 14 ? v.slice(0, 14) + '…' : v}
                        />
                        <Tooltip content={<BenchmarkTooltip />} />
                        <Bar dataKey="scenario" radius={[0, 6, 6, 0]}>
                          {barData.map((entry, i) => (
                            <Cell key={i} fill={readingColor(entry.reading).bar} />
                          ))}
                        </Bar>
                        {barData.map((entry, i) => (
                          <ReferenceLine
                            key={i}
                            x={entry.benchmark}
                            stroke="#94a3b8"
                            strokeDasharray="4 3"
                            strokeWidth={1.5}
                          />
                        ))}
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={styles.chartPlaceholder}>Run a scenario to generate the benchmark chart.</div>
                  )}
                </div>
              </div>
            </div>

            {/* Comparison table */}
            <div style={styles.card}>
              <div style={styles.chartHeader}>
                <div style={styles.sectionEyebrow}>Benchmark comparison</div>
                <h3 style={styles.chartTitle}>Your scenario vs reference points</h3>
              </div>
              {!result ? (
                <div style={styles.chartPlaceholder}>Run a scenario to generate the comparison table.</div>
              ) : (
                <div style={styles.tableWrapper}>
                  <table style={styles.table}>
                    <thead>
                      <tr>
                        <th style={styles.th}>Metric</th>
                        <th style={styles.th}>Scenario</th>
                        <th style={styles.th}>Reference</th>
                        <th style={styles.th}>Gap</th>
                        <th style={styles.th}>Reading</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.comparison_table.map((row) => (
                        <tr key={row.key}>
                          <td style={styles.tdMetric}>
                            {row.metric_label}
                          </td>
                          <td style={styles.td}>{row.scenario_value}</td>
                          <td style={styles.td}>
                            {row.benchmark_value}
                            <div style={styles.benchmarkLabel}>{row.benchmark_label}</div>
                          </td>
                          <td style={styles.td}>
                            <span style={{
                              color: row.gap_pct === null ? '#94a3b8' :
                                (row.lower_is_better ? (row.gap_pct < 0 ? '#16a34a' : '#dc2626') : (row.gap_pct > 0 ? '#16a34a' : '#dc2626')),
                              fontWeight: '700',
                              fontSize: '13px',
                            }}>
                              {row.gap_pct !== null ? `${row.gap_pct > 0 ? '+' : ''}${row.gap_pct}%` : '—'}
                            </span>
                          </td>
                          <td style={styles.td}>
                            <span style={readingPillStyle(row.reading)}>{row.reading}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p style={styles.tableNote}>
                    Gap = (scenario − benchmark) / benchmark × 100.{' '}
                    Green = favorable direction. Red = unfavorable direction.
                  </p>
                </div>
              )}
            </div>

            {/* Strengths and watchouts */}
            <div style={styles.bottomGrid}>
              <div style={styles.card}>
                <div style={styles.sectionEyebrow}>Strengths</div>
                <h3 style={styles.bottomTitle}>What supports the case</h3>
                {!result ? (
                  <p style={styles.bottomText}>Run a scenario to see the positive signals.</p>
                ) : (
                  <ul style={styles.list}>
                    {result.strengths.map((item, i) => (
                      <li key={i} style={styles.listItem}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>

              <div style={styles.card}>
                <div style={styles.sectionEyebrow}>Watchouts</div>
                <h3 style={styles.bottomTitle}>What still needs validation</h3>
                {!result ? (
                  <p style={styles.bottomText}>Run a scenario to see the benchmark gaps.</p>
                ) : (
                  <ul style={styles.list}>
                    {result.watchouts.map((item, i) => (
                      <li key={i} style={styles.listItem}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {/* Model caveats */}
            {result && (
              <div style={styles.card}>
                <div style={styles.sectionEyebrow}>Model limits</div>
                <h3 style={styles.bottomTitle}>What this prototype cannot tell you</h3>
                <ul style={styles.list}>
                  {result.model_caveats.map((c, i) => (
                    <li key={i} style={styles.listItem}>{c}</li>
                  ))}
                </ul>
                <p style={{ ...styles.bottomText, marginTop: '14px', fontStyle: 'italic' }}>
                  {result.methodology_note}
                </p>
              </div>
            )}

            {!result && (
              <div style={styles.card}>
                <div style={styles.sectionEyebrow}>Method note</div>
                <h3 style={styles.bottomTitle}>How to read this prototype</h3>
                <p style={styles.bottomText}>
                  This prototype compares scenario implications to explicit references — not a certified forecast.
                  All metrics are heuristic indexes. Benchmarks are illustrative anchors, not official standards.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── KPI Card ────────────────────────────────────────────────────────────────
function KpiCard({ title, value, subtitle, benchmark, reading }) {
  const hasReading = reading != null
  return (
    <div style={{
      ...styles.kpiCard,
      borderTop: hasReading ? `3px solid ${readingColor(reading).bar}` : '3px solid #e2e8f0',
    }}>
      <div style={styles.kpiLabel}>{title}</div>
      <div style={styles.kpiValue}>{value}</div>
      <div style={styles.kpiSubtitle}>{subtitle}</div>
      {benchmark && <div style={styles.kpiBenchmark}>{benchmark}</div>}
      {hasReading && (
        <div style={{ marginTop: '10px' }}>
          <span style={readingPillStyle(reading)}>{reading}</span>
        </div>
      )}
    </div>
  )
}

// ── Styles ───────────────────────────────────────────────────────────────────
const styles = {
  page: {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #edf4ff 0%, #f8fbff 45%, #ffffff 100%)',
    fontFamily: 'Inter, Arial, sans-serif',
    color: '#0f172a',
  },
  container: {
    maxWidth: '1320px',
    margin: '0 auto',
    padding: '24px 24px 48px',
  },
  disclaimer: {
    background: '#fffbeb',
    border: '1px solid #fcd34d',
    borderRadius: '14px',
    padding: '12px 18px',
    marginBottom: '20px',
    fontSize: '13px',
    color: '#78350f',
    lineHeight: '1.5',
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  disclaimerBadge: {
    background: '#f59e0b',
    color: 'white',
    borderRadius: '6px',
    padding: '3px 8px',
    fontSize: '11px',
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    whiteSpace: 'nowrap',
  },
  topBar: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: '0px',
  },
  logoCentered: {
    height: '160px',
    objectFit: 'contain',
  },
  hero: {
    marginBottom: '28px',
  },
  title: {
    fontSize: '52px',
    lineHeight: '1',
    margin: '0 0 14px 0',
    letterSpacing: '-1.8px',
    color: '#0f172a',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: '18px',
    maxWidth: '860px',
    lineHeight: '1.6',
    color: '#475569',
    margin: '0 auto',
    textAlign: 'center',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: '380px 1fr',
    gap: '24px',
    alignItems: 'start',
  },
  leftColumn: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  rightColumn: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  card: {
    background: 'rgba(255,255,255,0.82)',
    borderRadius: '20px',
    padding: '24px',
    border: '1px solid rgba(226,232,240,0.8)',
    boxShadow: '0 12px 40px rgba(15, 23, 42, 0.07)',
    backdropFilter: 'blur(10px)',
  },
  darkCard: {
    background: 'linear-gradient(135deg, #0b1736 0%, #111c44 100%)',
    color: 'white',
    borderRadius: '20px',
    padding: '24px',
    boxShadow: '0 12px 40px rgba(11, 23, 54, 0.2)',
  },
  darkEyebrow: {
    fontSize: '11px',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    opacity: 0.65,
    marginBottom: '10px',
    fontWeight: '700',
  },
  darkTitle: {
    fontSize: '22px',
    fontWeight: '700',
    marginBottom: '12px',
    lineHeight: '1.3',
  },
  darkText: {
    margin: 0,
    color: 'rgba(255,255,255,0.78)',
    lineHeight: '1.65',
    fontSize: '14px',
  },
  heroResultCard: {
    background: 'linear-gradient(135deg, rgba(255,255,255,0.92) 0%, rgba(246,250,255,0.95) 100%)',
    borderRadius: '20px',
    padding: '26px',
    border: '1px solid rgba(226,232,240,0.9)',
    boxShadow: '0 12px 40px rgba(15, 23, 42, 0.07)',
  },
  sectionHeader: {
    marginBottom: '16px',
  },
  sectionEyebrow: {
    fontSize: '11px',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    color: '#64748b',
    marginBottom: '8px',
    fontWeight: '700',
  },
  sectionTitle: {
    margin: 0,
    fontSize: '26px',
    letterSpacing: '-0.4px',
    color: '#0f172a',
  },
  resultHeadline: {
    margin: '0 0 12px 0',
    fontSize: '28px',
    letterSpacing: '-0.6px',
    color: '#0f172a',
    lineHeight: '1.25',
  },
  resultSubtext: {
    margin: 0,
    color: '#475569',
    lineHeight: '1.65',
    fontSize: '15px',
  },
  label: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginTop: '18px',
    marginBottom: '6px',
    fontWeight: '700',
    fontSize: '14px',
    color: '#1e293b',
  },
  unitBadge: {
    background: '#f1f5f9',
    color: '#64748b',
    borderRadius: '6px',
    padding: '2px 7px',
    fontSize: '11px',
    fontWeight: '600',
  },
  input: {
    width: '100%',
    padding: '12px 14px',
    borderRadius: '12px',
    border: '1px solid #cbd5e1',
    fontSize: '15px',
    background: '#ffffff',
    color: '#0f172a',
    boxSizing: 'border-box',
  },
  inputHint: {
    margin: '5px 0 0 0',
    fontSize: '12px',
    color: '#94a3b8',
    lineHeight: '1.5',
  },
  button: {
    marginTop: '22px',
    width: '100%',
    padding: '14px',
    borderRadius: '14px',
    border: 'none',
    background: 'linear-gradient(135deg, #0b1736 0%, #10204b 100%)',
    color: 'white',
    fontSize: '15px',
    fontWeight: '700',
    cursor: 'pointer',
    boxShadow: '0 8px 24px rgba(11, 23, 54, 0.22)',
    opacity: 1,
    transition: 'opacity 0.2s',
  },
  error: {
    color: '#dc2626',
    marginTop: '12px',
    fontWeight: '600',
    fontSize: '14px',
  },
  kpiGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '14px',
  },
  kpiCard: {
    background: 'rgba(255,255,255,0.88)',
    padding: '18px',
    borderRadius: '18px',
    border: '1px solid rgba(226,232,240,0.9)',
    boxShadow: '0 8px 24px rgba(15, 23, 42, 0.05)',
    boxSizing: 'border-box',
  },
  kpiLabel: {
    fontSize: '12px',
    color: '#64748b',
    marginBottom: '12px',
    fontWeight: '600',
    lineHeight: '1.4',
  },
  kpiValue: {
    fontSize: '30px',
    fontWeight: '800',
    color: '#0f172a',
    marginBottom: '8px',
  },
  kpiSubtitle: {
    fontSize: '12px',
    color: '#64748b',
    lineHeight: '1.4',
  },
  kpiBenchmark: {
    fontSize: '11px',
    color: '#94a3b8',
    marginTop: '4px',
    fontStyle: 'italic',
  },
  narrativeCard: {
    background: 'rgba(255,255,255,0.82)',
    borderRadius: '18px',
    padding: '20px 24px',
    border: '1px solid #fcd34d',
    boxShadow: '0 8px 24px rgba(15, 23, 42, 0.05)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '16px',
  },
  narrativeLeft: {
    flex: 1,
  },
  narrativeRight: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    gap: '8px',
  },
  narrativeTitle: {
    fontSize: '16px',
    fontWeight: '700',
    color: '#0f172a',
    marginBottom: '6px',
  },
  narrativeNote: {
    fontSize: '12px',
    color: '#78350f',
    margin: 0,
    lineHeight: '1.5',
    maxWidth: '480px',
  },
  narrativeValue: {
    fontSize: '36px',
    fontWeight: '800',
    color: '#0f172a',
  },
  chartGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '20px',
  },
  chartHeader: {
    marginBottom: '12px',
  },
  chartTitle: {
    margin: '0 0 4px 0',
    fontSize: '20px',
    letterSpacing: '-0.3px',
    color: '#0f172a',
  },
  chartNote: {
    margin: 0,
    fontSize: '12px',
    color: '#94a3b8',
    lineHeight: '1.45',
  },
  chartBox: {
    width: '100%',
    height: '280px',
  },
  chartPlaceholder: {
    width: '100%',
    minHeight: '120px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#94a3b8',
    background: '#f8fafc',
    borderRadius: '14px',
    textAlign: 'center',
    padding: '20px',
    boxSizing: 'border-box',
    fontSize: '14px',
  },
  tableWrapper: {
    overflowX: 'auto',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '14px',
  },
  th: {
    textAlign: 'left',
    padding: '10px 10px',
    borderBottom: '1px solid #e2e8f0',
    color: '#64748b',
    fontSize: '11px',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    fontWeight: '700',
  },
  td: {
    padding: '13px 10px',
    borderBottom: '1px solid #f1f5f9',
    color: '#334155',
    verticalAlign: 'top',
    fontSize: '14px',
  },
  tdMetric: {
    padding: '13px 10px',
    borderBottom: '1px solid #f1f5f9',
    color: '#0f172a',
    fontWeight: '700',
    verticalAlign: 'top',
    fontSize: '13px',
    maxWidth: '160px',
  },
  benchmarkLabel: {
    fontSize: '11px',
    color: '#94a3b8',
    marginTop: '4px',
    lineHeight: '1.4',
  },
  tableNote: {
    margin: '12px 0 0 0',
    fontSize: '11px',
    color: '#94a3b8',
    fontStyle: 'italic',
  },
  bottomGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '20px',
  },
  bottomTitle: {
    margin: '0 0 14px 0',
    fontSize: '22px',
    letterSpacing: '-0.4px',
    color: '#0f172a',
  },
  bottomText: {
    margin: 0,
    color: '#475569',
    lineHeight: '1.7',
    fontSize: '15px',
  },
  list: {
    margin: 0,
    paddingLeft: '18px',
    color: '#475569',
  },
  listItem: {
    marginBottom: '12px',
    lineHeight: '1.6',
    fontSize: '14px',
  },
}
