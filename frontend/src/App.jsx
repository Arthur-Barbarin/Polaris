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

  const scoreColor = useMemo(() => {
    if (!result) return '#0f172a'
    if (result.viability_score >= 65) return '#16a34a'
    if (result.viability_score >= 50) return '#f59e0b'
    return '#dc2626'
  }, [result])

  const scoreLabel = useMemo(() => {
    if (!result) return 'Awaiting scenario run'
    if (result.viability_score >= 65) return 'Promising concept'
    if (result.viability_score >= 50) return 'Needs refinement'
    return 'Concept at risk'
  }, [result])

  const insightLabel = useMemo(() => {
    if (!result) return 'No insight yet'
    if (result.viability_score >= 65) return 'Strong investment narrative'
    if (result.viability_score >= 50) return 'Sensitive to assumptions'
    return 'High-risk narrative'
  }, [result])

  const radarData = useMemo(() => {
    if (!result) return []
    return [
      { metric: 'Economics', value: Math.max(0, Math.min(100, 200 - result.unit_cost)) },
      { metric: 'Adoption', value: result.adoption },
      { metric: 'Climate', value: Math.max(0, Math.min(100, 100 - result.emissions)) },
      { metric: 'Investor', value: result.investor_score },
      { metric: 'Technical', value: Math.max(0, Math.min(100, 100 - result.technical_risk)) },
    ]
  }, [result])

  const scatterData = useMemo(() => {
    if (!result) return []
    return [
      {
        unit_cost: result.unit_cost,
        technical_risk: result.technical_risk,
        size: Math.max(80, result.investor_score * 4),
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
            A decision-support demo for aerospace and climate transport teams. Adjust assumptions,
            run the scenario, and translate technical uncertainty into a decision-oriented readout.
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

              <label style={styles.label}>SAF share</label>
              <input type="number" value={safShare} onChange={(e) => setSafShare(e.target.value)} style={styles.input} />

              <label style={styles.label}>Hydrogen readiness</label>
              <input type="number" value={hydrogenReadiness} onChange={(e) => setHydrogenReadiness(e.target.value)} style={styles.input} />

              <label style={styles.label}>Electricity price</label>
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
              <div style={styles.darkEyebrow}>Why this feels useful</div>
              <div style={styles.darkTitle}>Decision-ready, not just technical</div>
              <p style={styles.darkText}>
                This prototype is meant to show how Polaris can turn uncertain engineering assumptions
                into a credible recommendation for founders, CTOs, or investors.
              </p>
            </div>
          </div>

          <div style={styles.rightColumn}>
            <div style={styles.heroResultCard}>
              <div>
                <div style={styles.sectionEyebrow}>Decision signal</div>
                <h2 style={styles.resultHeadline}>{scoreLabel}</h2>
                <p style={styles.resultSubtext}>
                  {result
                    ? result.executive_summary
                    : 'Run a scenario to generate a viability score, executive summary, and visual trade-off view.'}
                </p>
              </div>

              <div style={{ ...styles.scorePill, borderColor: scoreColor }}>
                <div style={styles.scorePillLabel}>Viability</div>
                <div style={{ ...styles.scorePillValue, color: scoreColor }}>
                  {result ? result.viability_score : '--'}
                </div>
              </div>
            </div>

            <div style={styles.kpiGrid}>
              <KpiCard title="Adoption" value={result ? result.adoption : '--'} subtitle="Market-fit proxy" />
              <KpiCard title="Unit cost" value={result ? result.unit_cost : '--'} subtitle="Relative cost index" />
              <KpiCard title="Emissions" value={result ? result.emissions : '--'} subtitle="Residual footprint" />
              <KpiCard title="Insight" value={insightLabel} subtitle="Decision framing" largeText />
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
                <div style={styles.sectionEyebrow}>Recommendation</div>
                <h3 style={styles.bottomTitle}>{result ? result.recommendation : 'No recommendation yet'}</h3>
                <p style={styles.bottomText}>
                  {result
                    ? 'This recommendation is generated by the backend model based on cost, emissions, risk, and investor-facing attractiveness.'
                    : 'The recommendation will appear here after running a scenario.'}
                </p>
              </div>

              <div style={styles.card}>
                <div style={styles.sectionEyebrow}>Executive summary</div>
                <h3 style={styles.bottomTitle}>Client-ready interpretation</h3>
                <p style={styles.bottomText}>
                  {result
                    ? result.executive_summary
                    : 'This area is designed to feel presentation-ready for a startup, investor, or strategy conversation.'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function KpiCard({ title, value, subtitle, largeText = false }) {
  return (
    <div style={styles.kpiCard}>
      <div style={styles.kpiLabel}>{title}</div>
      <div
        style={{
          ...styles.kpiValue,
          fontSize: largeText ? '22px' : '40px',
          lineHeight: largeText ? '1.25' : '1',
        }}
      >
        {value}
      </div>
      <div style={styles.kpiSubtitle}>{subtitle}</div>
    </div>
  )
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
  logoContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '14px',
  },
  
  logo: {
    height: '200px',
    width: '200px',
    objectFit: 'contain',
    
  },
  
  logoText: {
    fontSize: '18px',
    fontWeight: '800',
    color: '#0f172a',
    letterSpacing: '0.2px',
  },
  
  logoSubtext: {
    fontSize: '13px',
    color: '#64748b',
    marginTop: '4px',
  },
  smallTag: {
    fontSize: '13px',
    color: '#475569',
    background: 'rgba(255,255,255,0.65)',
    border: '1px solid rgba(148,163,184,0.2)',
    padding: '8px 12px',
    borderRadius: '999px',
    backdropFilter: 'blur(8px)',
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
  },
  subtitle: {
    fontSize: '20px',
    maxWidth: '1000px',
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
  scorePill: {
    minWidth: '150px',
    padding: '16px 18px',
    borderRadius: '22px',
    border: '2px solid #0f172a',
    background: 'white',
    textAlign: 'center',
    boxShadow: '0 12px 30px rgba(15, 23, 42, 0.08)',
  },
  scorePillLabel: {
    fontSize: '13px',
    color: '#64748b',
    marginBottom: '6px',
  },
  scorePillValue: {
    fontSize: '42px',
    fontWeight: '800',
    lineHeight: '1',
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
    maxWidth: '700px',
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
    fontSize: '40px',
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
    height: '100%',
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
  logoCentered: {
    height: '200px',       // ajuste si tu veux plus grand
    objectFit: 'contain',
  },
}