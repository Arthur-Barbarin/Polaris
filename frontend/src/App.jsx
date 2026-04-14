import logo from './assets/polaris_logo.png'
import { useMemo, useState } from 'react'
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ScatterChart,
  Scatter,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
} from 'recharts'

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
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          concept,
          saf_share: Number(safShare),
          hydrogen_readiness: Number(hydrogenReadiness),
          electricity_price: Number(electricityPrice),
          carbon_price: Number(carbonPrice),
          demand_growth: Number(demandGrowth),
        }),
      })

      if (!response.ok) {
        throw new Error('Backend error')
      }

      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError('Unable to reach the backend. Make sure FastAPI is running.')
    } finally {
      setLoading(false)
    }
  }

  const radarData = useMemo(() => {
    if (!result) return []

    return [
      {
        metric: 'Cost position',
        value: Math.max(0, Math.min(100, 200 - result.outputs.unit_cost)),
      },
      {
        metric: 'Adoption',
        value: result.outputs.adoption,
      },
      {
        metric: 'Climate',
        value: Math.max(0, Math.min(100, 100 - result.outputs.emissions)),
      },
      {
        metric: 'Investor',
        value: result.outputs.investor_score,
      },
      {
        metric: 'Technical',
        value: Math.max(0, Math.min(100, 100 - result.outputs.technical_risk)),
      },
    ]
  }, [result])

  const scatterData = useMemo(() => {
    if (!result) return []

    return [
      {
        unit_cost: result.outputs.unit_cost,
        technical_risk: result.outputs.technical_risk,
        size: Math.max(80, result.outputs.investor_score * 4),
      },
    ]
  }, [result])

  return (
    <div style={styles.page}>
      <div style={styles.container}>
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
          <div style={styles.leftColumn}>
            <div style={styles.card}>
              <div style={styles.sectionHeader}>
                <div>
                  <div style={styles.sectionEyebrow}>Inputs</div>
                  <h2 style={styles.sectionTitle}>Scenario controls</h2>
                </div>
              </div>

              <label style={styles.label}>Concept</label>
              <select value={concept} onChange={(e) => setConcept(e.target.value)} style={styles.input}>
                <option value="regional">Regional aircraft</option>
                <option value="narrowbody">Low-emission narrowbody</option>
                <option value="drone">Advanced air mobility / drone</option>
              </select>

              <label style={styles.label}>SAF share (%)</label>
              <input type="number" value={safShare} onChange={(e) => setSafShare(e.target.value)} style={styles.input} />

              <label style={styles.label}>Hydrogen readiness</label>
              <input type="number" value={hydrogenReadiness} onChange={(e) => setHydrogenReadiness(e.target.value)} style={styles.input} />

              <label style={styles.label}>Electricity price exposure</label>
              <input type="number" value={electricityPrice} onChange={(e) => setElectricityPrice(e.target.value)} style={styles.input} />

              <label style={styles.label}>Carbon price</label>
              <input type="number" value={carbonPrice} onChange={(e) => setCarbonPrice(e.target.value)} style={styles.input} />

              <label style={styles.label}>Demand growth</label>
              <input type="number" value={demandGrowth} onChange={(e) => setDemandGrowth(e.target.value)} style={styles.input} />

              <button onClick={runScenario} style={styles.button}>
                {loading ? 'Running…' : 'Run scenario'}
              </button>

              {error && <p style={styles.error}>{error}</p>}
            </div>

            <div style={styles.darkCard}>
              <div style={styles.darkEyebrow}>Positioning</div>
              <div style={styles.darkTitle}>Structured assumptions, not black-box scoring</div>
              <p style={styles.darkText}>
                Polaris is most credible when it translates assumptions into explicit implications and benchmark comparisons, rather than into a single opaque score.
              </p>
            </div>
          </div>

          <div style={styles.rightColumn}>
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

            <div style={styles.kpiGrid}>
              <KpiCard
                title="Unit cost index"
                value={result ? result.outputs.unit_cost : '--'}
                subtitle="Lower is better"
              />
              <KpiCard
                title="Emissions proxy"
                value={result ? result.outputs.emissions : '--'}
                subtitle="Lower is better"
              />
              <KpiCard
                title="Technical risk"
                value={result ? result.outputs.technical_risk : '--'}
                subtitle="Lower is better"
              />
              <KpiCard
                title="Adoption potential"
                value={result ? result.outputs.adoption : '--'}
                subtitle="Higher is better"
              />
            </div>

            <div style={styles.card}>
              <div style={styles.chartHeader}>
                <div>
                  <div style={styles.sectionEyebrow}>Benchmark comparison</div>
                  <h3 style={styles.chartTitle}>Your scenario vs reference points</h3>
                </div>
              </div>

              {!result ? (
                <div style={styles.chartPlaceholder}>
                  Run a scenario to generate the comparison table.
                </div>
              ) : (
                <div style={styles.tableWrapper}>
                  <table style={styles.table}>
                    <thead>
                      <tr>
                        <th style={styles.th}>Metric</th>
                        <th style={styles.th}>Your scenario</th>
                        <th style={styles.th}>Reference</th>
                        <th style={styles.th}>Reading</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.comparison_table.map((row) => (
                        <tr key={row.metric}>
                          <td style={styles.tdMetric}>{row.metric}</td>
                          <td style={styles.td}>
                            {row.scenario_value} {row.scenario_unit}
                          </td>
                          <td style={styles.td}>
                            {row.benchmark_value} {row.benchmark_unit}
                            <div style={styles.benchmarkLabel}>{row.benchmark_label}</div>
                          </td>
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

            <div style={styles.chartGrid}>
              <div style={styles.card}>
                <div style={styles.chartHeader}>
                  <div>
                    <div style={styles.sectionEyebrow}>Balanced view</div>
                    <h3 style={styles.chartTitle}>Scenario profile</h3>
                  </div>
                </div>

                <div style={styles.chartBox}>
                  {result ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart data={radarData}>
                        <PolarGrid />
                        <PolarAngleAxis dataKey="metric" />
                        <PolarRadiusAxis domain={[0, 100]} />
                        <Radar dataKey="value" stroke="#0f172a" fill="#0f172a" fillOpacity={0.35} />
                      </RadarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={styles.chartPlaceholder}>Run a scenario to generate the radar chart.</div>
                  )}
                </div>
              </div>

              <div style={styles.card}>
                <div style={styles.chartHeader}>
                  <div>
                    <div style={styles.sectionEyebrow}>Trade-off</div>
                    <h3 style={styles.chartTitle}>Cost vs technical risk</h3>
                  </div>
                </div>

                <div style={styles.chartBox}>
                  {result ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 10 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis type="number" dataKey="unit_cost" name="Unit cost" />
                        <YAxis type="number" dataKey="technical_risk" name="Technical risk" />
                        <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                        <Scatter data={scatterData} fill="#0f172a" />
                      </ScatterChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={styles.chartPlaceholder}>Run a scenario to generate the trade-off chart.</div>
                  )}
                </div>
              </div>
            </div>

            <div style={styles.bottomGrid}>
              <div style={styles.card}>
                <div style={styles.sectionEyebrow}>Strengths</div>
                <h3 style={styles.bottomTitle}>What supports the case</h3>
                {!result ? (
                  <p style={styles.bottomText}>Run a scenario to see the positive signals.</p>
                ) : (
                  <ul style={styles.list}>
                    {result.strengths.map((item) => (
                      <li key={item} style={styles.listItem}>
                        {item}
                      </li>
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
                    {result.watchouts.map((item) => (
                      <li key={item} style={styles.listItem}>
                        {item}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            <div style={styles.card}>
              <div style={styles.sectionEyebrow}>Method note</div>
              <h3 style={styles.bottomTitle}>How to read this prototype</h3>
              <p style={styles.bottomText}>
                {result
                  ? result.methodology_note
                  : 'This prototype is intended to compare scenario implications to explicit references, not to serve as a certified forecast.'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function KpiCard({ title, value, subtitle }) {
  return (
    <div style={styles.kpiCard}>
      <div style={styles.kpiLabel}>{title}</div>
      <div style={styles.kpiValue}>{value}</div>
      <div style={styles.kpiSubtitle}>{subtitle}</div>
    </div>
  )
}

function readingPillStyle(reading) {
  let background = '#e2e8f0'
  let color = '#334155'

  if (reading === 'Better than benchmark') {
    background = '#dcfce7'
    color = '#166534'
  } else if (reading === 'Near benchmark') {
    background = '#fef3c7'
    color = '#92400e'
  } else if (reading === 'Above benchmark' || reading === 'Below benchmark') {
    background = '#fee2e2'
    color = '#991b1b'
  }

  return {
    display: 'inline-block',
    padding: '6px 10px',
    borderRadius: '999px',
    fontSize: '12px',
    fontWeight: '700',
    background,
    color,
    whiteSpace: 'nowrap',
  }
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
    padding: '32px 24px 48px',
  },
  topBar: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: '0px',
  },
  logoCentered: {
    height: '180px',
    objectFit: 'contain',
  },
  hero: {
    marginBottom: '28px',
  },
  title: {
    fontSize: '58px',
    lineHeight: '1',
    margin: '0 0 14px 0',
    letterSpacing: '-1.8px',
    color: '#0f172a',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: '20px',
    maxWidth: '900px',
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
    background: 'rgba(255,255,255,0.78)',
    borderRadius: '24px',
    padding: '24px',
    border: '1px solid rgba(226,232,240,0.8)',
    boxShadow: '0 18px 50px rgba(15, 23, 42, 0.08)',
    backdropFilter: 'blur(10px)',
  },
  darkCard: {
    background: 'linear-gradient(135deg, #0b1736 0%, #111c44 100%)',
    color: 'white',
    borderRadius: '24px',
    padding: '24px',
    boxShadow: '0 18px 50px rgba(11, 23, 54, 0.22)',
  },
  darkEyebrow: {
    fontSize: '12px',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    opacity: 0.7,
    marginBottom: '10px',
  },
  darkTitle: {
    fontSize: '24px',
    fontWeight: '700',
    marginBottom: '12px',
  },
  darkText: {
    margin: 0,
    color: 'rgba(255,255,255,0.82)',
    lineHeight: '1.6',
    fontSize: '15px',
  },
  heroResultCard: {
    background: 'linear-gradient(135deg, rgba(255,255,255,0.88) 0%, rgba(246,250,255,0.92) 100%)',
    borderRadius: '24px',
    padding: '24px',
    border: '1px solid rgba(226,232,240,0.9)',
    boxShadow: '0 18px 50px rgba(15, 23, 42, 0.08)',
    display: 'flex',
    justifyContent: 'space-between',
    gap: '20px',
    alignItems: 'center',
  },
  sectionHeader: {
    marginBottom: '8px',
  },
  sectionEyebrow: {
    fontSize: '12px',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    color: '#64748b',
    marginBottom: '8px',
    fontWeight: '700',
  },
  sectionTitle: {
    margin: 0,
    fontSize: '28px',
    letterSpacing: '-0.5px',
    color: '#0f172a',
  },
  resultHeadline: {
    margin: '0 0 10px 0',
    fontSize: '34px',
    letterSpacing: '-0.8px',
    color: '#0f172a',
  },
  resultSubtext: {
    margin: 0,
    color: '#475569',
    lineHeight: '1.6',
    fontSize: '16px',
    maxWidth: '800px',
  },
  label: {
    display: 'block',
    marginTop: '16px',
    marginBottom: '8px',
    fontWeight: '700',
    fontSize: '15px',
    color: '#1e293b',
  },
  input: {
    width: '100%',
    padding: '14px 14px',
    borderRadius: '14px',
    border: '1px solid #cbd5e1',
    fontSize: '15px',
    background: '#ffffff',
    color: '#0f172a',
    boxSizing: 'border-box',
  },
  button: {
    marginTop: '22px',
    width: '100%',
    padding: '15px',
    borderRadius: '16px',
    border: 'none',
    background: 'linear-gradient(135deg, #0b1736 0%, #10204b 100%)',
    color: 'white',
    fontSize: '16px',
    fontWeight: '700',
    cursor: 'pointer',
    boxShadow: '0 14px 28px rgba(11, 23, 54, 0.22)',
  },
  error: {
    color: '#dc2626',
    marginTop: '12px',
    fontWeight: '600',
  },
  kpiGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '16px',
  },
  kpiCard: {
    background: 'rgba(255,255,255,0.84)',
    padding: '22px',
    borderRadius: '22px',
    border: '1px solid rgba(226,232,240,0.9)',
    boxShadow: '0 12px 30px rgba(15, 23, 42, 0.05)',
    minHeight: '132px',
    boxSizing: 'border-box',
  },
  kpiLabel: {
    fontSize: '14px',
    color: '#64748b',
    marginBottom: '16px',
    fontWeight: '600',
  },
  kpiValue: {
    fontSize: '34px',
    fontWeight: '800',
    color: '#0f172a',
    marginBottom: '10px',
    wordBreak: 'break-word',
  },
  kpiSubtitle: {
    fontSize: '13px',
    color: '#64748b',
    lineHeight: '1.4',
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
    margin: 0,
    fontSize: '24px',
    letterSpacing: '-0.4px',
    color: '#0f172a',
  },
  chartBox: {
    width: '100%',
    height: '300px',
  },
  chartPlaceholder: {
    width: '100%',
    minHeight: '140px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#64748b',
    background: '#f8fafc',
    borderRadius: '18px',
    textAlign: 'center',
    padding: '20px',
    boxSizing: 'border-box',
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
    padding: '12px 10px',
    borderBottom: '1px solid #e2e8f0',
    color: '#475569',
    fontSize: '12px',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  td: {
    padding: '14px 10px',
    borderBottom: '1px solid #e2e8f0',
    color: '#334155',
    verticalAlign: 'top',
  },
  tdMetric: {
    padding: '14px 10px',
    borderBottom: '1px solid #e2e8f0',
    color: '#0f172a',
    fontWeight: '700',
    verticalAlign: 'top',
  },
  benchmarkLabel: {
    fontSize: '12px',
    color: '#64748b',
    marginTop: '4px',
  },
  bottomGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '20px',
  },
  bottomTitle: {
    margin: '0 0 12px 0',
    fontSize: '28px',
    letterSpacing: '-0.6px',
    color: '#0f172a',
  },
  bottomText: {
    margin: 0,
    color: '#475569',
    lineHeight: '1.7',
    fontSize: '16px',
  },
  list: {
    margin: 0,
    paddingLeft: '18px',
    color: '#475569',
  },
  listItem: {
    marginBottom: '10px',
    lineHeight: '1.6',
  },
}