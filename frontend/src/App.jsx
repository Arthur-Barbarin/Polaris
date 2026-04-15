import logo from './assets/Polaris_logo.png'
import { useState } from 'react'

// ── Option metadata ──────────────────────────────────────────────────────────

const CONCEPT_OPTIONS = [
  {
    value: 'narrowbody',
    label: 'Narrowbody — A320 / B737-family',
    hint: '2019 fleet avg: 88 gCO₂/RPK · Ref flight: 165 seats × 800 km · Source: IATA Net-Zero 2023',
  },
  {
    value: 'regional',
    label: 'Regional — ATR-72 / E175-class',
    hint: '2019 fleet avg: 110 gCO₂/RPK · Ref flight: 75 seats × 500 km · Source: ICAO CAEP/12 2022',
  },
  {
    value: 'widebody',
    label: 'Long-haul widebody — A350 / B787-class',
    hint: '2019 fleet avg: 72 gCO₂/RPK · Ref flight: 280 seats × 8,000 km · Source: IATA Net-Zero 2023',
  },
]

const SAF_TYPE_OPTIONS = [
  {
    value: 'hefa',
    label: 'Bio-SAF — HEFA',
    hint: '75% WTW CO₂ saving · TRL 9 · Commercially available · Source: ICAO CORSIA 2022',
  },
  {
    value: 'mix',
    label: 'Mixed blend — Bio-SAF + PtL',
    hint: '82% WTW CO₂ saving · TRL 8 · Transition mix · Source: IATA CR 2024',
  },
  {
    value: 'ptl',
    label: 'Power-to-Liquid — PtL',
    hint: '90% WTW CO₂ saving · TRL 6 · Pilot-stage only · Source: ICAO CORSIA 2022',
  },
]

const TECH_OPTIONS = [
  {
    value: 'conservative',
    label: 'Conservative — 0.9%/yr',
    hint: 'In-pipeline aircraft only · Low deployment risk · Source: ICAO CAEP/12 2022',
  },
  {
    value: 'moderate',
    label: 'Moderate — 1.3%/yr',
    hint: 'New aircraft + ATM improvements · Source: ICAO + IATA roadmap assumptions',
  },
  {
    value: 'advanced',
    label: 'Advanced — 2.0%/yr',
    hint: 'Next-generation concepts required · Higher deployment risk · Source: IATA CR 2024',
  },
]

const DEMAND_OPTIONS = [
  {
    value: 'low',
    label: 'Low — 2.1%/yr CAGR',
    hint: 'IEA Net-Zero pathway · Source: IATA CR 2024',
  },
  {
    value: 'mid',
    label: 'Mid — 2.9%/yr CAGR',
    hint: 'IATA S2 central case · Source: IATA CR 2024',
  },
  {
    value: 'high',
    label: 'High — 3.8%/yr CAGR',
    hint: 'ICAO LTAG-style growth · Source: IATA CR 2024',
  },
]

// ── Helpers ──────────────────────────────────────────────────────────────────

function readingColor(reading) {
  const GREEN = new Set([
    'Better than benchmark',
    'Meets or exceeds ReFuelEU mandate',
    'Cost-competitive under EU ETS',
    'Commercially available',
  ])
  const AMBER = new Set([
    'Near benchmark',
    'Near ReFuelEU mandate (within 5pp)',
    'Near commercial readiness',
  ])
  if (GREEN.has(reading)) return { bg: '#dcfce7', text: '#166534', border: '#22c55e' }
  if (AMBER.has(reading)) return { bg: '#fef3c7', text: '#92400e', border: '#f59e0b' }
  return { bg: '#fee2e2', text: '#991b1b', border: '#ef4444' }
}

function readingPillStyle(reading) {
  if (!reading) return {}
  const c = readingColor(reading)
  return {
    display: 'inline-block',
    padding: '4px 10px',
    borderRadius: '999px',
    fontSize: '11px',
    fontWeight: '700',
    background: c.bg,
    color: c.text,
    whiteSpace: 'nowrap',
  }
}

function SelectInput({ label, value, onChange, options }) {
  const selected = options.find((o) => o.value === value)
  return (
    <div>
      <label style={styles.label}>{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} style={styles.input}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {selected?.hint && <p style={styles.inputHint}>{selected.hint}</p>}
    </div>
  )
}

function KpiCard({ title, value, unit, subtitle, benchmark, reading }) {
  const color = reading ? readingColor(reading).border : '#e2e8f0'
  return (
    <div style={{ ...styles.kpiCard, borderTop: `3px solid ${color}` }}>
      <div style={styles.kpiLabel}>{title}</div>
      <div style={styles.kpiValueRow}>
        <span style={styles.kpiValue}>{value}</span>
        {unit && <span style={styles.kpiUnit}>{unit}</span>}
      </div>
      <div style={styles.kpiSubtitle}>{subtitle}</div>
      {benchmark && <div style={styles.kpiBenchmark}>{benchmark}</div>}
      {reading && (
        <div style={{ marginTop: '10px' }}>
          <span style={readingPillStyle(reading)}>{reading}</span>
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [concept, setConcept] = useState('narrowbody')
  const [targetYear, setTargetYear] = useState(2030)
  const [safSharePct, setSafSharePct] = useState(20)
  const [safType, setSafType] = useState('hefa')
  const [techScenario, setTechScenario] = useState('moderate')
  const [demandScenario, setDemandScenario] = useState('mid')
  const [carbonPrice, setCarbonPrice] = useState(80)

  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeInsightTab, setActiveInsightTab] = useState('strengths')

  async function runScenario() {
    setLoading(true)
    setError('')
    try {
      const response = await fetch('http://127.0.0.1:8000/run-scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          concept,
          target_year: Number(targetYear),
          saf_share_pct: Number(safSharePct),
          saf_type: safType,
          tech_scenario: techScenario,
          demand_scenario: demandScenario,
          carbon_price_usd_tco2: Number(carbonPrice),
        }),
      })

      if (!response.ok) {
        const text = await response.text()
        throw new Error(text || 'Backend error')
      }

      const data = await response.json()
      setResult(data)
    } catch {
      setError('Unable to reach the backend. Make sure FastAPI is running on port 8000.')
    } finally {
      setLoading(false)
    }
  }

  const insightItems =
    result && activeInsightTab === 'strengths'
      ? result.strengths
      : result && activeInsightTab === 'watchouts'
      ? result.watchouts
      : []

  return (
    <div style={styles.page}>
      <div style={styles.container}>
        <div style={styles.disclaimer}>
          <span style={styles.disclaimerBadge}>Prototype</span>
          Quantitative decision-support tool based on published aviation roadmaps. Outputs are benchmarked quantities, not a synthetic score.
        </div>

        <div style={styles.topBar}>
          <img src={logo} alt="Polaris logo" style={styles.logoCentered} />
        </div>

        <div style={styles.hero}>
          <h1 style={styles.title}>Scenario Explorer</h1>
          <p style={styles.subtitle}>
            Test aviation decarbonization assumptions and compare them against explicit reference benchmarks.
          </p>
        </div>

        <div style={styles.grid}>
          <div style={styles.leftColumn}>
            <div style={styles.card}>
              <div style={styles.sectionHeader}>
                <div style={styles.sectionEyebrow}>Inputs</div>
                <h2 style={styles.sectionTitle}>Scenario parameters</h2>
              </div>

              <SelectInput
                label="Aircraft concept"
                value={concept}
                onChange={setConcept}
                options={CONCEPT_OPTIONS}
              />

              <div>
                <label style={styles.label}>Target year</label>
                <select
                  value={targetYear}
                  onChange={(e) => setTargetYear(Number(e.target.value))}
                  style={styles.input}
                >
                  <option value={2030}>2030</option>
                  <option value={2035}>2035</option>
                  <option value={2050}>2050</option>
                </select>
                <p style={styles.inputHint}>Sets the roadmap benchmark and policy milestone year.</p>
              </div>

              <div>
                <label style={styles.label}>
                  SAF share
                  <span style={styles.unitBadge}>% of fuel mix</span>
                  <span style={styles.valueBadge}>{safSharePct}%</span>
                </label>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={1}
                  value={safSharePct}
                  onChange={(e) => setSafSharePct(e.target.value)}
                  style={styles.slider}
                />
                <div style={styles.sliderTicks}>
                  <span>0%</span>
                  <span>50%</span>
                  <span>100%</span>
                </div>
                <p style={styles.inputHint}>
                  Fuel mix share assumed to come from SAF.
                </p>
              </div>

              <SelectInput
                label="SAF pathway"
                value={safType}
                onChange={setSafType}
                options={SAF_TYPE_OPTIONS}
              />

              <SelectInput
                label="Technology scenario"
                value={techScenario}
                onChange={setTechScenario}
                options={TECH_OPTIONS}
              />

              <SelectInput
                label="Demand scenario"
                value={demandScenario}
                onChange={setDemandScenario}
                options={DEMAND_OPTIONS}
              />

              <div>
                <label style={styles.label}>
                  Carbon price
                  <span style={styles.unitBadge}>$/tCO₂</span>
                  <span style={styles.valueBadge}>${carbonPrice}</span>
                </label>
                <input
                  type="range"
                  min={0}
                  max={200}
                  step={5}
                  value={carbonPrice}
                  onChange={(e) => setCarbonPrice(e.target.value)}
                  style={styles.slider}
                />
                <div style={styles.sliderTicks}>
                  <span>$0</span>
                  <span>$100</span>
                  <span>$200</span>
                </div>
                <p style={styles.inputHint}>
                  Used to compare SAF premium to carbon-cost pressure.
                </p>
              </div>

              <button
                onClick={runScenario}
                disabled={loading}
                style={{ ...styles.button, opacity: loading ? 0.7 : 1 }}
              >
                {loading ? 'Computing…' : 'Run scenario'}
              </button>

              {error && <p style={styles.error}>{error}</p>}
            </div>
          </div>

          <div style={styles.rightColumn}>
            <div style={styles.heroResultCard}>
              <div style={styles.sectionEyebrow}>Scenario implication</div>
              <h2 style={styles.resultHeadline}>
                {result
                  ? result.headline
                  : 'Run a scenario to see the key decision signal'}
              </h2>
              <p style={styles.resultSubtext}>
                {result
                  ? result.interpretation
                  : 'This demo is designed to show what a set of assumptions implies relative to published climate, policy, and cost benchmarks.'}
              </p>
            </div>

            <div style={styles.kpiGrid}>
              <KpiCard
                title="CO₂ intensity"
                value={result ? String(result.outputs.co2_intensity_gco2_rpk) : '--'}
                unit="gCO₂/RPK"
                subtitle="Lower is better"
                benchmark={result ? `Moderate ${result.target_year} benchmark: ${result.benchmarks.co2_moderate_gco2_rpk}` : ''}
                reading={result ? result.comparison_table.find((r) => r.key === 'co2_intensity')?.reading : null}
              />
              <KpiCard
                title="CO₂ reduction"
                value={result ? `${result.outputs.co2_reduction_from_2019_pct}%` : '--'}
                unit=""
                subtitle="vs 2019 baseline"
                benchmark={result ? `2019 baseline: ${result.benchmarks.co2_2019_baseline} gCO₂/RPK` : ''}
                reading={result ? result.comparison_table.find((r) => r.key === 'co2_intensity')?.reading : null}
              />
              <KpiCard
                title="SAF cost premium"
                value={result ? `$${result.outputs.saf_cost_premium_usd_per_seat.toFixed(2)}` : '--'}
                unit="/seat"
                subtitle="Reference flight"
                benchmark={result ? `EU ETS equivalent: $${result.outputs.eu_ets_carbon_cost_per_seat.toFixed(2)}/seat` : ''}
                reading={result ? result.comparison_table.find((r) => r.key === 'saf_cost_premium')?.reading : null}
              />
              <KpiCard
                title="Policy gap"
                value={
                  result
                    ? `${result.outputs.gap_vs_refueleu_pp > 0 ? '+' : ''}${result.outputs.gap_vs_refueleu_pp}pp`
                    : '--'
                }
                unit=""
                subtitle="vs ReFuelEU mandate"
                benchmark={result ? `${result.inputs.saf_share_pct}% assumed vs ${result.benchmarks.refueleu_saf_target_pct}% target` : ''}
                reading={result ? result.comparison_table.find((r) => r.key === 'saf_policy_alignment')?.reading : null}
              />
            </div>

            <div style={styles.card}>
              <div style={styles.sectionEyebrow}>Benchmark comparison</div>
              <h3 style={styles.blockTitle}>How this scenario compares</h3>

              {!result ? (
                <div style={styles.placeholder}>Run a scenario to generate the comparison table.</div>
              ) : (
                <div style={styles.tableWrapper}>
                  <table style={styles.table}>
                    <thead>
                      <tr>
                        <th style={styles.th}>Metric</th>
                        <th style={styles.th}>You</th>
                        <th style={styles.th}>Benchmark</th>
                        <th style={styles.th}>Signal</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.comparison_table.map((row) => (
                        <tr key={row.key}>
                          <td style={styles.tdMetric}>{shortMetricLabel(row.metric_label)}</td>
                          <td style={styles.td}>{formatScenarioValue(row)}</td>
                          <td style={styles.td}>{formatBenchmarkValue(row)}</td>
                          <td style={styles.td}>
                            <span style={readingPillStyle(row.reading)}>{row.reading}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div style={styles.card}>
              <div style={styles.sectionEyebrow}>Insights</div>
              <div style={styles.tabHeader}>
                <button
                  style={{
                    ...styles.tabButton,
                    ...(activeInsightTab === 'strengths' ? styles.tabButtonActive : {}),
                  }}
                  onClick={() => setActiveInsightTab('strengths')}
                >
                  Strengths
                </button>
                <button
                  style={{
                    ...styles.tabButton,
                    ...(activeInsightTab === 'watchouts' ? styles.tabButtonActive : {}),
                  }}
                  onClick={() => setActiveInsightTab('watchouts')}
                >
                  Watchouts
                </button>
              </div>

              {!result ? (
                <div style={styles.placeholder}>Run a scenario to see the key decision insights.</div>
              ) : (
                <ul style={styles.insightList}>
                  {insightItems.map((item, i) => (
                    <li key={i} style={styles.insightListItem}>
                      {item}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function shortMetricLabel(label) {
  const map = {
    'CO₂ emissions intensity': 'CO₂ intensity',
    'SAF mandate compliance': 'SAF compliance',
    'SAF cost premium per seat': 'SAF cost premium',
    'SAF pathway technology readiness': 'SAF pathway TRL',
  }
  return map[label] || label
}

function formatScenarioValue(row) {
  if (row.key === 'co2_intensity') return `${row.scenario_value} gCO₂/RPK`
  if (row.key === 'saf_policy_alignment') return `${row.scenario_value}%`
  if (row.key === 'saf_cost_premium') return `$${Number(row.scenario_value).toFixed(2)}/seat`
  if (row.key === 'saf_trl') return `TRL ${row.scenario_value}/9`
  return row.scenario_value
}

function formatBenchmarkValue(row) {
  if (row.key === 'co2_intensity') return `${row.benchmark_value} gCO₂/RPK`
  if (row.key === 'saf_policy_alignment') return `${row.benchmark_value}%`
  if (row.key === 'saf_cost_premium') return `$${Number(row.benchmark_value).toFixed(2)}/seat`
  if (row.key === 'saf_trl') return 'TRL 9'
  return row.benchmark_value
}

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
    padding: '24px 24px 56px',
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
    alignItems: 'flex-start',
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
    marginTop: '1px',
  },
  topBar: {
    display: 'flex',
    justifyContent: 'center',
    marginBottom: '0px',
  },
  logoCentered: {
    height: '150px',
    objectFit: 'contain',
  },
  hero: {
    marginBottom: '28px',
  },
  title: {
    fontSize: '50px',
    lineHeight: '1',
    margin: '0 0 14px 0',
    letterSpacing: '-1.6px',
    color: '#0f172a',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: '17px',
    maxWidth: '760px',
    lineHeight: '1.65',
    color: '#475569',
    margin: '0 auto',
    textAlign: 'center',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: '400px minmax(0, 1fr)',
    gap: '24px',
    alignItems: 'start',
  },
  leftColumn: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
    minWidth: 0,
  },
  rightColumn: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
    minWidth: 0,
  },
  card: {
    background: 'rgba(255,255,255,0.84)',
    borderRadius: '20px',
    padding: '24px',
    border: '1px solid rgba(226,232,240,0.85)',
    boxShadow: '0 12px 40px rgba(15, 23, 42, 0.07)',
    minWidth: 0,
    overflow: 'hidden',
  },
  heroResultCard: {
    background: 'linear-gradient(135deg, rgba(255,255,255,0.92) 0%, rgba(246,250,255,0.95) 100%)',
    borderRadius: '20px',
    padding: '26px',
    border: '1px solid rgba(226,232,240,0.9)',
    boxShadow: '0 12px 40px rgba(15, 23, 42, 0.07)',
    minWidth: 0,
    overflow: 'hidden',
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
    fontSize: '24px',
    letterSpacing: '-0.4px',
    color: '#0f172a',
  },
  resultHeadline: {
    margin: '0 0 12px 0',
    fontSize: '24px',
    letterSpacing: '-0.4px',
    color: '#0f172a',
    lineHeight: '1.25',
    maxWidth: '100%',
    overflowWrap: 'anywhere',
  },
  resultSubtext: {
    margin: 0,
    color: '#475569',
    lineHeight: '1.65',
    fontSize: '14px',
    maxWidth: '100%',
    overflowWrap: 'anywhere',
  },
  label: {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '6px',
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
  valueBadge: {
    background: '#dbeafe',
    color: '#1d4ed8',
    borderRadius: '6px',
    padding: '2px 7px',
    fontSize: '11px',
    fontWeight: '700',
  },
  input: {
    width: '100%',
    padding: '11px 14px',
    borderRadius: '12px',
    border: '1px solid #cbd5e1',
    fontSize: '14px',
    background: '#ffffff',
    color: '#0f172a',
    boxSizing: 'border-box',
  },
  slider: {
    width: '100%',
    marginTop: '2px',
    accentColor: '#0b1736',
  },
  sliderTicks: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '11px',
    color: '#94a3b8',
    marginTop: '2px',
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
  },
  error: {
    color: '#dc2626',
    marginTop: '12px',
    fontWeight: '600',
    fontSize: '13px',
    lineHeight: '1.5',
  },
  kpiGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
    gap: '14px',
  },
  kpiCard: {
    background: 'rgba(255,255,255,0.9)',
    padding: '18px',
    borderRadius: '18px',
    border: '1px solid rgba(226,232,240,0.9)',
    boxSizing: 'border-box',
    minWidth: 0,
    textAlign: 'center',
  },
  kpiLabel: {
    fontSize: '11px',
    color: '#64748b',
    marginBottom: '10px',
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    lineHeight: '1.4',
  },
  kpiValueRow: {
    display: 'flex',
    alignItems: 'baseline',
    justifyContent: 'center',
    gap: '5px',
    marginBottom: '8px',
    flexWrap: 'wrap',
  },
  kpiValue: {
    fontSize: '28px',
    fontWeight: '800',
    color: '#0f172a',
    lineHeight: '1',
  },
  kpiUnit: {
    fontSize: '12px',
    color: '#64748b',
    fontWeight: '500',
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
    lineHeight: '1.4',
  },
  blockTitle: {
    margin: '0 0 14px 0',
    fontSize: '20px',
    letterSpacing: '-0.3px',
    color: '#0f172a',
  },
  placeholder: {
    minHeight: '100px',
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
    tableLayout: 'fixed',
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
    padding: '12px 10px',
    borderBottom: '1px solid #f1f5f9',
    color: '#334155',
    verticalAlign: 'top',
    fontSize: '14px',
    overflowWrap: 'anywhere',
  },
  tdMetric: {
    padding: '12px 10px',
    borderBottom: '1px solid #f1f5f9',
    color: '#0f172a',
    fontWeight: '700',
    verticalAlign: 'top',
    fontSize: '13px',
    overflowWrap: 'anywhere',
  },
  tabHeader: {
    display: 'flex',
    gap: '10px',
    marginBottom: '16px',
  },
  tabButton: {
    padding: '10px 14px',
    borderRadius: '999px',
    border: '1px solid #cbd5e1',
    background: '#ffffff',
    color: '#475569',
    fontSize: '13px',
    fontWeight: '700',
    cursor: 'pointer',
  },
  tabButtonActive: {
    background: '#0b1736',
    color: 'white',
    border: '1px solid #0b1736',
  },
  insightList: {
    margin: 0,
    paddingLeft: '20px',
    color: '#475569',
    textAlign: 'left',
  },
  insightListItem: {
    marginBottom: '12px',
    lineHeight: '1.6',
    fontSize: '14px',
    textAlign: 'left',
  },
}