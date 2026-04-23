import logo from './assets/Polaris_logo.png'
import { useState, useMemo, useEffect } from 'react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Cell, ReferenceLine,
} from 'recharts'

const API = 'http://127.0.0.1:8002'

// ── Option metadata ──────────────────────────────────────────────────────────

const USE_CASE_OPTIONS = [
  { value: 'inspection', label: 'Inspection', hint: 'Power lines · Wind turbines · Pipelines · Infrastructure' },
  { value: 'delivery',   label: 'Last-mile delivery', hint: 'Package delivery · Logistics · E-commerce' },
  { value: 'agriculture',label: 'Agriculture', hint: 'Crop spraying · Precision mapping · Yield monitoring' },
]

const HUMAN_ALT_OPTIONS = {
  inspection: [
    { value: 'helicopter',  label: 'Manned helicopter',        hint: '$2,500/hr fully loaded · [PwC-2016]' },
    { value: 'rope_access', label: 'Rope access team',         hint: '$4,000/turbine or structure · [PwC-2016; industry 2024]' },
    { value: 'ground_crew', label: 'Ground crew (bucket truck)', hint: '$150/hr · 2.5 km/hr coverage · [PwC-2016]' },
  ],
  agriculture: [
    { value: 'aerial', label: 'Manned crop duster', hint: '$15/acre · US aerial application avg · [MU-EXT 2024]' },
    { value: 'ground', label: 'Ground sprayer',     hint: '$6/acre · Self-propelled equipment · [MU-EXT 2024]' },
  ],
}

const PLATFORM_OPTIONS = [
  { value: 'light',        label: 'Light — DJI Mavic 3 Enterprise class',    hint: '$6,500 · max 0.9 kg · 42 min · VLOS 5 km / BVLOS 10 km' },
  { value: 'professional', label: 'Professional — DJI Matrice 350 RTK class', hint: '$20,000 · max 2.7 kg · 55 min · VLOS 8 km / BVLOS 20 km' },
  { value: 'heavy',        label: 'Heavy — DJI Matrice 4E / Wingtra class',   hint: '$50,000 · max 5.0 kg · 57 min · VLOS 12 km / BVLOS 40 km' },
]

const BVLOS_OPTIONS = [
  { value: 'not_authorized', label: 'Not authorized', hint: 'No waiver held — BVLOS operations not permitted' },
  { value: 'waiver_pending', label: 'Waiver pending',  hint: 'FAA §107.31 application submitted — awaiting approval' },
  { value: 'authorized',     label: 'Authorized',      hint: 'Current waiver held — Part 108 permit (2026-27+)' },
]

const GEOGRAPHY_OPTIONS = [
  { value: 'urban',    label: 'Urban',    hint: 'Dense metro · LAANC authorization required' },
  { value: 'suburban', label: 'Suburban', hint: 'Mixed residential/commercial' },
  { value: 'rural',    label: 'Rural',    hint: 'Low-density · Agricultural · Open terrain' },
  { value: 'remote',   label: 'Remote',   hint: 'Off-grid · High delivery cost baseline' },
]

const LABOR_OPTIONS = [
  { value: 'low',      label: 'Low (×0.7)',      hint: 'Developing / low-wage market' },
  { value: 'standard', label: 'Standard (×1.0)', hint: 'US market reference' },
  { value: 'high',     label: 'High (×1.5)',     hint: 'High-cost metro · Offshore · Union labor' },
]

// ── Verdict helpers ──────────────────────────────────────────────────────────

function verdictStyle(verdict) {
  if (verdict === 'GO')          return { bg: '#dcfce7', text: '#166534', border: '#22c55e', dot: '#22c55e' }
  if (verdict === 'CONDITIONAL') return { bg: '#fef3c7', text: '#92400e', border: '#f59e0b', dot: '#f59e0b' }
  return                                { bg: '#fee2e2', text: '#991b1b', border: '#ef4444', dot: '#ef4444' }
}

function verdictIcon(verdict) {
  if (verdict === 'GO')          return '✓'
  if (verdict === 'CONDITIONAL') return '◐'
  return '✕'
}

// ── Shared UI helpers ────────────────────────────────────────────────────────

function SelectInput({ label, value, onChange, options, hint }) {
  const sel = options.find(o => o.value === value)
  return (
    <div style={{ marginTop: 18 }}>
      <label style={S.label}>{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)} style={S.input}>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <p style={S.hint}>{hint || sel?.hint || ''}</p>
    </div>
  )
}

function KpiCard({ label, value, unit, sub, accent }) {
  return (
    <div style={{ ...S.kpiCard, borderTop: `3px solid ${accent || '#e2e8f0'}` }}>
      <div style={S.kpiLabel}>{label}</div>
      <div style={S.kpiValueRow}>
        <span style={S.kpiValue}>{value}</span>
        {unit && <span style={S.kpiUnit}>{unit}</span>}
      </div>
      {sub && <div style={S.kpiSub}>{sub}</div>}
    </div>
  )
}

function Shimmer({ w = '100%', h = 18, mt = 0 }) {
  return (
    <div style={{
      height: h, width: w, borderRadius: 6, marginTop: mt,
      background: 'linear-gradient(90deg,#f1f5f9 25%,#e2e8f0 50%,#f1f5f9 75%)',
      backgroundSize: '200% 100%', animation: 'shimmer 1.4s infinite',
    }} />
  )
}

function SensitivityTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12,
      padding: '10px 14px', fontSize: 13, boxShadow: '0 4px 16px rgba(0,0,0,.1)', maxWidth: 280 }}>
      <div style={{ fontWeight: 700, marginBottom: 6, color: '#0f172a' }}>{d.label}</div>
      <div style={{ color: '#475569' }}>{d.detail}</div>
    </div>
  )
}

// ── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  // ── Input state ───────────────────────────────────────────────────────────
  const [useCase,        setUseCase]        = useState('inspection')
  const [humanAlt,       setHumanAlt]       = useState('helicopter')
  const [platformTier,   setPlatformTier]   = useState('professional')
  const [missionRange,   setMissionRange]   = useState(1.0)
  const [payload,        setPayload]        = useState(0.5)
  const [bvlosStatus,    setBvlosStatus]    = useState('not_authorized')
  const [annualMissions, setAnnualMissions] = useState(200)
  const [geography,      setGeography]      = useState('rural')
  const [laborMult,      setLaborMult]      = useState('standard')
  const [pointAsset,     setPointAsset]     = useState(false)

  // Reset human_alternative when use_case changes
  useEffect(() => {
    if (useCase === 'inspection')  setHumanAlt('helicopter')
    if (useCase === 'agriculture') setHumanAlt('aerial')
  }, [useCase])

  // Auto-set point_asset when rope_access selected
  useEffect(() => {
    setPointAsset(humanAlt === 'rope_access')
  }, [humanAlt])

  // ── Result / UI state ─────────────────────────────────────────────────────
  const [result,      setResult]      = useState(null)
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState('')
  const [mainTab,     setMainTab]     = useState('overview')
  const [insightTab,  setInsightTab]  = useState('strengths')
  const [aiNarrative, setAiNarrative] = useState(null)
  const [aiLoading,   setAiLoading]   = useState(false)
  const [chatMsgs,    setChatMsgs]    = useState([])
  const [chatInput,   setChatInput]   = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  // ── Run scenario ──────────────────────────────────────────────────────────
  async function runScenario() {
    setLoading(true)
    setError('')
    setResult(null)
    setAiNarrative(null)
    setChatMsgs([])
    try {
      const body = {
        use_case:          useCase,
        human_alternative: useCase === 'delivery' ? 'helicopter' : humanAlt,
        platform_tier:     platformTier,
        mission_range_km:  Number(missionRange),
        payload_kg:        Number(payload),
        bvlos_status:      bvlosStatus,
        annual_missions:   Number(annualMissions),
        geography,
        labor_multiplier:  laborMult,
        point_asset_mission: pointAsset,
      }
      const res = await fetch(`${API}/run-scenario`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setResult(data)

      // Non-blocking AI narrative
      setAiLoading(true)
      fetch(`${API}/generate-narrative`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_result: data }),
      })
        .then(r => r.json())
        .then(n => { setAiNarrative(n); setAiLoading(false) })
        .catch(() => setAiLoading(false))

    } catch (e) {
      setError(`Unable to reach the backend. Make sure FastAPI is running on port 8002.\n${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  // ── Chat ──────────────────────────────────────────────────────────────────
  async function sendChat(e) {
    e?.preventDefault()
    const q = chatInput.trim()
    if (!q || !result || chatLoading) return
    const userMsg = { role: 'user', content: q }
    const nextHistory = [...chatMsgs, userMsg]
    setChatMsgs(nextHistory)
    setChatInput('')
    setChatLoading(true)
    try {
      const resp = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, scenario_context: result, history: chatMsgs }),
      })
      const data = await resp.json()
      const reply = data.error ? `${data.reply}\n\nDebug: ${data.error}` : data.reply
      setChatMsgs([...nextHistory, { role: 'assistant', content: reply }])
    } catch (err) {
      setChatMsgs([...nextHistory, { role: 'assistant', content: `Network error: ${err.message}` }])
    } finally {
      setChatLoading(false)
    }
  }

  // ── Derived data ──────────────────────────────────────────────────────────
  const verdict = result?.decision?.verdict ?? null
  const vs = verdict ? verdictStyle(verdict) : null

  const insightSource = aiNarrative ?? result
  const insightItems = useMemo(() => {
    if (!insightSource) return []
    if (insightTab === 'strengths')  return insightSource.strengths  ?? []
    if (insightTab === 'watchouts')  return insightSource.watchouts  ?? []
    if (insightTab === 'changes')    return (aiNarrative ?? {}).what_changes_the_decision ?? []
    return []
  }, [insightSource, insightTab, aiNarrative])

  const sensitivityBarData = useMemo(() => {
    const top3 = result?.resolution?.sensitivity?.top3_drivers ?? []
    return top3.map((d, i) => ({
      name: d.label.length > 22 ? d.label.slice(0, 20) + '…' : d.label,
      label: d.label,
      value: d.swing_usd_annual,
      detail: d.detail,
      fill: i === 0 ? '#0b1736' : i === 1 ? '#3b82f6' : '#8b5cf6',
    }))
  }, [result])

  // Cost breakdown comparison data
  const costCompareData = useMemo(() => {
    if (!result) return []
    const m = result.metrics
    const breakdown = m.drone_doc_breakdown ?? {}
    return [
      { name: 'Drone — DOC',   value: m.drone_doc_per_mission_usd,  fill: '#0b1736' },
      { name: 'Human alternative', value: m.human_cost_per_mission_usd, fill: '#94a3b8' },
    ]
  }, [result])

  const humanAltOptions = HUMAN_ALT_OPTIONS[useCase] ?? []

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={S.page}>
      <div style={S.container}>

        {/* Disclaimer */}
        <div style={S.disclaimer}>
          <span style={S.disclaimerBadge}>Prototype</span>
          Decision-support tool for commercial drone deployment. Costs derived from FAA, PwC, MU Extension, and Barclays published data. Not a certified engineering or financial model.
        </div>

        {/* Logo + title */}
        <div style={{ textAlign: 'center', marginBottom: 8 }}>
          <img src={logo} alt="Polaris" style={{ height: 140, objectFit: 'contain' }} />
        </div>
        <div style={S.hero}>
          <h1 style={S.title}>Drone Deployment Engine</h1>
          <p style={S.subtitle}>
            Should you deploy drones here, now, and how?<br />
            Get a traceable GO / NO-GO verdict with the exact binding constraint and resolution path.
          </p>
        </div>

        {/* Two-column layout */}
        <div style={S.grid}>

          {/* ── LEFT: Inputs ──────────────────────────────────────────────── */}
          <div style={S.left}>
            <div style={S.card}>
              <div style={S.eyebrow}>Inputs</div>
              <h2 style={S.sectionTitle}>Scenario parameters</h2>

              <SelectInput label="Use case" value={useCase} onChange={setUseCase} options={USE_CASE_OPTIONS} />

              {useCase !== 'delivery' && (
                <SelectInput
                  label="Human alternative"
                  value={humanAlt}
                  onChange={setHumanAlt}
                  options={humanAltOptions}
                />
              )}

              {useCase === 'delivery' && (
                <div style={{ marginTop: 18 }}>
                  <label style={S.label}>Human alternative</label>
                  <div style={S.infoBox}>Auto-derived from geography: van/courier cost per stop.</div>
                </div>
              )}

              <SelectInput label="Platform tier" value={platformTier} onChange={setPlatformTier} options={PLATFORM_OPTIONS} />

              {/* Mission range */}
              <div style={{ marginTop: 18 }}>
                <label style={S.label}>
                  Mission range (one-way)
                  <span style={S.unitBadge}>km</span>
                  <span style={S.valueBadge}>{Number(missionRange).toFixed(1)} km</span>
                </label>
                <input type="range" min={0.5} max={20} step={0.5}
                  value={missionRange} onChange={e => setMissionRange(e.target.value)} style={S.slider} />
                <div style={S.sliderTicks}><span>0.5 km</span><span>10 km</span><span>20 km</span></div>
                <p style={S.hint}>
                  VLOS practical limit: 1.5 km [FAA-107 §107.31]. Beyond this, BVLOS required.
                </p>
              </div>

              {/* Payload */}
              <div style={{ marginTop: 18 }}>
                <label style={S.label}>
                  Payload
                  <span style={S.unitBadge}>kg</span>
                  <span style={S.valueBadge}>{Number(payload).toFixed(1)} kg</span>
                </label>
                <input type="range" min={0.1} max={5} step={0.1}
                  value={payload} onChange={e => setPayload(e.target.value)} style={S.slider} />
                <div style={S.sliderTicks}><span>0.1 kg</span><span>2.5 kg</span><span>5 kg</span></div>
                <p style={S.hint}>Sensor package (inspection) or cargo (delivery).</p>
              </div>

              <SelectInput label="BVLOS authorization" value={bvlosStatus} onChange={setBvlosStatus} options={BVLOS_OPTIONS} />
              <SelectInput label="Geography" value={geography} onChange={setGeography} options={GEOGRAPHY_OPTIONS} />
              <SelectInput label="Labor cost context" value={laborMult} onChange={setLaborMult} options={LABOR_OPTIONS} />

              {/* Annual missions */}
              <div style={{ marginTop: 18 }}>
                <label style={S.label}>
                  Annual missions
                  <span style={S.valueBadge}>{Number(annualMissions).toLocaleString()}/yr</span>
                </label>
                <input type="range" min={10} max={2000} step={10}
                  value={annualMissions} onChange={e => setAnnualMissions(e.target.value)} style={S.slider} />
                <div style={S.sliderTicks}><span>10</span><span>1,000</span><span>2,000</span></div>
                <p style={S.hint}>Affects depreciation per mission and break-even dynamics.</p>
              </div>

              <button onClick={runScenario} disabled={loading}
                style={{ ...S.button, opacity: loading ? 0.7 : 1 }}>
                {loading ? 'Computing…' : 'Run scenario →'}
              </button>

              {error && <p style={S.error}>{error}</p>}
            </div>
          </div>

          {/* ── RIGHT: Results ─────────────────────────────────────────────── */}
          <div style={S.right}>

            {/* ── BLOCK A: Decision signal ─────────────────────────────────── */}
            <div style={{
              ...S.card,
              borderLeft: vs ? `5px solid ${vs.border}` : '5px solid #e2e8f0',
              background: vs
                ? `linear-gradient(135deg, ${vs.bg}44 0%, rgba(255,255,255,0.95) 60%)`
                : 'rgba(255,255,255,0.84)',
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>

                {/* Verdict badge */}
                <div style={{
                  minWidth: 80, textAlign: 'center',
                  background: vs ? vs.bg : '#f1f5f9',
                  border: `2px solid ${vs ? vs.border : '#e2e8f0'}`,
                  borderRadius: 16, padding: '12px 14px',
                }}>
                  <div style={{ fontSize: 28, fontWeight: 900, color: vs ? vs.text : '#94a3b8', lineHeight: 1 }}>
                    {verdict ? verdictIcon(verdict) : '?'}
                  </div>
                  <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.1em',
                    color: vs ? vs.text : '#94a3b8', marginTop: 6, textTransform: 'uppercase' }}>
                    {verdict ?? 'No run'}
                  </div>
                </div>

                {/* Headline + constraint */}
                <div style={{ flex: 1, minWidth: 200 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <div style={S.eyebrow}>Decision signal</div>
                    {aiNarrative?.ai_available && <span style={S.aiBadge}>✦ AI</span>}
                  </div>

                  {aiLoading ? (
                    <><Shimmer /><Shimmer w="75%" mt={8} h={14} /></>
                  ) : (
                    <>
                      <h2 style={S.headline}>
                        {aiNarrative?.headline
                          || result?.decision?.explanation
                          || 'Run a scenario to see the deployment verdict.'}
                      </h2>
                      {result?.decision?.binding_constraint && result.decision.binding_constraint !== 'None' && (
                        <div style={{ marginTop: 10 }}>
                          <span style={{
                            display: 'inline-block', padding: '4px 10px', borderRadius: 999,
                            fontSize: 12, fontWeight: 700,
                            background: vs?.bg, color: vs?.text,
                            border: `1px solid ${vs?.border}`,
                          }}>
                            ⚠ {result.decision.binding_constraint}
                          </span>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* Interpretation */}
              {(aiNarrative?.interpretation || result?.decision?.resolution_path) && (
                <p style={{ ...S.subtext, marginTop: 14, paddingTop: 14, borderTop: '1px solid #e2e8f0' }}>
                  {aiNarrative?.interpretation || result.decision.resolution_path}
                </p>
              )}
            </div>

            {/* ── Tabs ────────────────────────────────────────────────────── */}
            <div style={S.tabRow}>
              {['overview', 'sensitivity', 'details'].map(t => (
                <button key={t} onClick={() => setMainTab(t)}
                  style={{ ...S.tabBtn, ...(mainTab === t ? S.tabBtnActive : {}) }}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>

            {/* ── BLOCK B: Overview ────────────────────────────────────────── */}
            {mainTab === 'overview' && (
              <>
                {/* 4 KPI cards */}
                <div style={S.kpiGrid}>
                  <KpiCard
                    label="Drone DOC / mission"
                    value={result ? `$${result.metrics.drone_doc_per_mission_usd.toFixed(0)}` : '--'}
                    unit="/mission"
                    sub="Direct operating cost (all-in)"
                    accent="#0b1736"
                  />
                  <KpiCard
                    label="Human alternative"
                    value={result ? `$${result.metrics.human_cost_per_mission_usd.toFixed(0)}` : '--'}
                    unit="/mission"
                    sub={result?.metrics?.human_alternative ?? ''}
                    accent="#94a3b8"
                  />
                  <KpiCard
                    label="Cost savings"
                    value={result ? `${result.metrics.savings_pct > 0 ? '' : ''}${result.metrics.savings_pct.toFixed(1)}%` : '--'}
                    unit=""
                    sub={result ? `$${result.metrics.savings_per_mission_usd.toFixed(0)}/mission` : ''}
                    accent={result ? (result.metrics.savings_pct > 0 ? '#22c55e' : '#ef4444') : '#e2e8f0'}
                  />
                  <KpiCard
                    label="Annual savings"
                    value={result ? `$${(result.metrics.annual_savings_usd / 1000).toFixed(0)}k` : '--'}
                    unit="/yr"
                    sub={result ? `${annualMissions.toLocaleString()} missions/yr` : ''}
                    accent={result ? (result.metrics.annual_savings_usd > 0 ? '#22c55e' : '#ef4444') : '#e2e8f0'}
                  />
                </div>

                {/* Break-even row */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                  <KpiCard
                    label="Break-even volume"
                    value={result?.metrics?.break_even_missions != null
                      ? `${result.metrics.break_even_missions} missions`
                      : '—'}
                    unit=""
                    sub="To recover platform cost"
                    accent="#3b82f6"
                  />
                  <KpiCard
                    label="Platform payback"
                    value={result?.metrics?.platform_payback_months != null
                      ? `${result.metrics.platform_payback_months} mo`
                      : '—'}
                    unit=""
                    sub={`At ${Number(annualMissions).toLocaleString()} missions/yr`}
                    accent="#3b82f6"
                  />
                </div>

                {/* Cost comparison chart */}
                <div style={S.card}>
                  <div style={S.eyebrow}>Cost comparison</div>
                  <h3 style={S.blockTitle}>Drone DOC vs human alternative — per mission</h3>
                  {!result ? (
                    <div style={S.placeholder}>Run a scenario to see the cost comparison.</div>
                  ) : (
                    <div style={{ height: 180 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={costCompareData} layout="vertical"
                          margin={{ top: 8, right: 40, bottom: 8, left: 8 }}>
                          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                          <XAxis type="number" tickFormatter={v => `$${v.toLocaleString()}`}
                            tick={{ fontSize: 11 }} />
                          <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 11 }} />
                          <Tooltip formatter={v => [`$${Number(v).toFixed(2)}`, 'Cost/mission']} />
                          <Bar dataKey="value" radius={[0, 8, 8, 0]}>
                            {costCompareData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {/* DOC breakdown */}
                  {result?.metrics?.drone_doc_breakdown && (
                    <div style={{ marginTop: 16 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b',
                        textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>
                        DOC breakdown
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                        {Object.entries(result.metrics.drone_doc_breakdown)
                          .filter(([k]) => k !== 'total')
                          .map(([k, v]) => (
                            <div key={k} style={{
                              background: '#f8fafc', border: '1px solid #e2e8f0',
                              borderRadius: 10, padding: '7px 12px', fontSize: 12,
                            }}>
                              <span style={{ color: '#64748b', textTransform: 'capitalize' }}>
                                {k.replace('_', ' ')}
                              </span>{' '}
                              <span style={{ fontWeight: 700, color: '#0f172a' }}>
                                ${Number(v).toFixed(2)}
                              </span>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Benchmarks */}
                {result?.benchmarks && Object.keys(result.benchmarks).length > 0 && (
                  <div style={S.card}>
                    <div style={S.eyebrow}>Benchmark</div>
                    <h3 style={S.blockTitle}>Industry reference points</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {result.use_case === 'delivery' && result.benchmarks.viability_threshold_usd && (
                        <BenchmarkRow
                          label="Delivery viability threshold"
                          value={`$${result.metrics.drone_doc_per_mission_usd.toFixed(2)}/mission`}
                          benchmark={`<$${result.benchmarks.viability_threshold_usd}/delivery`}
                          reading={result.benchmarks.viability_reading}
                          source="[BARCLAYS] 2026"
                        />
                      )}
                      {result.inputs?.use_case === 'inspection' && result.benchmarks.expected_savings_range_pct && (
                        <BenchmarkRow
                          label="Expected savings range"
                          value={`${result.metrics.savings_pct.toFixed(1)}% actual`}
                          benchmark={`${result.benchmarks.expected_savings_range_pct} industry reference`}
                          reading={
                            result.metrics.savings_pct >= parseInt(result.benchmarks.expected_savings_range_pct)
                              ? 'Within expected range' : 'Below expected range'
                          }
                          source="[PwC-2016]"
                        />
                      )}
                      {result.inputs?.use_case === 'agriculture' && result.benchmarks.annual_acres_this_scenario != null && (
                        <BenchmarkRow
                          label="Annual acreage vs break-even"
                          value={`${Number(result.benchmarks.annual_acres_this_scenario).toLocaleString()} acres/yr`}
                          benchmark={`${result.benchmarks.breakeven_ownership_acres_yr.toLocaleString()} acres/yr ownership break-even`}
                          reading={result.benchmarks.above_breakeven ? 'Above break-even' : 'Below break-even'}
                          source="[MU-EXT] 2024"
                        />
                      )}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* ── BLOCK C: Sensitivity ─────────────────────────────────────── */}
            {mainTab === 'sensitivity' && (
              <>
                <div style={S.card}>
                  <div style={S.eyebrow}>Sensitivity analysis</div>
                  <h3 style={S.blockTitle}>Top 3 drivers — annual savings swing</h3>
                  <p style={{ fontSize: 13, color: '#64748b', margin: '0 0 16px 0', lineHeight: 1.6 }}>
                    Each bar shows the annual savings swing (USD) when that variable is changed.
                    The tallest bar is the lever that matters most for this deployment.
                  </p>
                  {!result ? (
                    <div style={S.placeholder}>Run a scenario to see sensitivity drivers.</div>
                  ) : (
                    <div style={{ height: 220 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={sensitivityBarData} layout="vertical"
                          margin={{ top: 8, right: 40, bottom: 8, left: 8 }}>
                          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                          <XAxis type="number"
                            tickFormatter={v => `$${(v / 1000).toFixed(0)}k`}
                            tick={{ fontSize: 11 }} />
                          <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 11 }} />
                          <Tooltip content={<SensitivityTooltip />} />
                          <Bar dataKey="value" radius={[0, 8, 8, 0]}>
                            {sensitivityBarData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>

                {/* BVLOS unlock highlight */}
                {result && (() => {
                  const unlock = result.resolution?.sensitivity?.bvlos_unlock_usd ?? 0
                  const note = result.resolution?.sensitivity?.bvlos_note ?? ''
                  if (unlock <= 0) return (
                    <div style={{ ...S.card, borderLeft: '4px solid #8b5cf6' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <div style={S.eyebrow}>BVLOS regulatory unlock</div>
                        <span style={{ ...S.aiBadge, background: 'linear-gradient(135deg,#7c3aed,#8b5cf6)' }}>
                          Part 108
                        </span>
                      </div>
                      <p style={{ fontSize: 13, color: '#475569', lineHeight: 1.6 }}>{note}</p>
                    </div>
                  )
                  return (
                    <div style={{ ...S.card, borderLeft: '4px solid #8b5cf6',
                      background: 'linear-gradient(135deg,rgba(139,92,246,0.06),rgba(255,255,255,0.95))' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <div style={S.eyebrow}>BVLOS regulatory unlock</div>
                        <span style={{ ...S.aiBadge, background: 'linear-gradient(135deg,#7c3aed,#8b5cf6)' }}>
                          Part 108
                        </span>
                      </div>
                      <div style={{ fontSize: 32, fontWeight: 900, color: '#6d28d9', letterSpacing: -1 }}>
                        +${unlock.toLocaleString()}/yr
                      </div>
                      <p style={{ fontSize: 13, color: '#475569', lineHeight: 1.6, marginTop: 8 }}>
                        {note}
                      </p>
                    </div>
                  )
                })()}

                {/* Volume sweep table */}
                {result?.resolution?.sensitivity?.volume_sweep && (
                  <div style={S.card}>
                    <div style={S.eyebrow}>Volume sensitivity</div>
                    <h3 style={S.blockTitle}>Annual savings at different mission volumes</h3>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                        <thead>
                          <tr>
                            {['Scenario', 'Missions / yr', 'Drone DOC', 'Annual savings'].map(h => (
                              <th key={h} style={S.th}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(result.resolution.sensitivity.volume_sweep).map(([label, row]) => (
                            <tr key={label}>
                              <td style={{ ...S.td, fontWeight: label === 'base volume' ? 700 : 400 }}>{label}</td>
                              <td style={S.td}>{row.annual_missions.toLocaleString()}</td>
                              <td style={S.td}>${Number(row.drone_doc).toFixed(2)}</td>
                              <td style={{
                                ...S.td, fontWeight: 700,
                                color: row.annual_savings > 0 ? '#16a34a' : '#dc2626',
                              }}>
                                {row.annual_savings > 0 ? '' : ''} ${Math.abs(row.annual_savings).toLocaleString()}
                                {row.annual_savings < 0 ? ' (loss)' : ''}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Labor sweep */}
                {result?.resolution?.sensitivity?.labor_sweep && (
                  <div style={S.card}>
                    <div style={S.eyebrow}>Labor cost sensitivity</div>
                    <h3 style={S.blockTitle}>Annual savings at different labor cost levels</h3>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                        <thead>
                          <tr>
                            {['Scenario', 'Human cost / mission', 'Annual savings'].map(h => (
                              <th key={h} style={S.th}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(result.resolution.sensitivity.labor_sweep).map(([label, row]) => (
                            <tr key={label}>
                              <td style={{ ...S.td, fontWeight: label === 'standard' ? 700 : 400 }}>{label}</td>
                              <td style={S.td}>${Number(row.human_cost).toFixed(2)}</td>
                              <td style={{
                                ...S.td, fontWeight: 700,
                                color: row.annual_savings > 0 ? '#16a34a' : '#dc2626',
                              }}>
                                ${Math.abs(row.annual_savings).toLocaleString()}
                                {row.annual_savings < 0 ? ' (loss)' : ''}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            )}

            {/* ── Details tab ───────────────────────────────────────────────── */}
            {mainTab === 'details' && (
              <div style={S.card}>
                <div style={S.eyebrow}>Details</div>
                <h3 style={S.blockTitle}>Full scenario breakdown</h3>
                {!result ? (
                  <div style={S.placeholder}>Run a scenario to see the full breakdown.</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                    <DetailSection title="Decision" rows={[
                      ['Verdict', result.decision.verdict],
                      ['Binding constraint', result.decision.binding_constraint],
                      ['Resolution path', result.decision.resolution_path],
                    ]} />
                    <DetailSection title="Core metrics" rows={[
                      ['Drone DOC / mission', `$${result.metrics.drone_doc_per_mission_usd.toFixed(2)}`],
                      ['Human alternative / mission', `$${result.metrics.human_cost_per_mission_usd.toFixed(2)}`],
                      ['Savings / mission', `$${result.metrics.savings_per_mission_usd.toFixed(2)} (${result.metrics.savings_pct.toFixed(1)}%)`],
                      ['Annual savings', `$${result.metrics.annual_savings_usd.toLocaleString()}`],
                      ['Break-even volume', result.metrics.break_even_missions != null ? `${result.metrics.break_even_missions} missions` : 'N/A'],
                      ['Platform payback', result.metrics.platform_payback_months != null ? `${result.metrics.platform_payback_months} months` : 'N/A'],
                    ]} />
                    <DetailSection title="Platform" rows={[
                      ['Tier', result.platform.tier],
                      ['Label', result.platform.label],
                      ['Acquisition cost', `$${result.platform.acquisition_cost_usd.toLocaleString()}`],
                      ['Max payload', `${result.platform.max_payload_kg} kg`],
                    ]} />
                    <DetailSection title="Regulatory context" rows={[
                      ['BVLOS required', String(result.regulatory_context.bvlos_required)],
                      ['BVLOS status', result.regulatory_context.bvlos_authorization_status],
                      ['VLOS practical limit', `${result.regulatory_context.vlos_practical_limit_km} km`],
                      ['Part 108 status', result.regulatory_context.part_108_status],
                      ['Urban LAANC required', String(result.regulatory_context.urban_laanc_required)],
                    ]} />
                    <p style={{ fontSize: 11, color: '#94a3b8', fontStyle: 'italic', lineHeight: 1.6 }}>
                      {result.methodology_note}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* ── Insights ──────────────────────────────────────────────────── */}
            <div style={S.card}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                <div style={S.eyebrow}>Insights</div>
                {aiNarrative?.ai_available && <span style={S.aiBadge}>✦ AI</span>}
              </div>
              <div style={S.tabRow}>
                {[
                  { key: 'strengths', label: 'Strengths' },
                  { key: 'watchouts', label: 'Watchouts' },
                  { key: 'changes',   label: 'What changes the decision' },
                ].map(t => (
                  <button key={t.key} onClick={() => setInsightTab(t.key)}
                    style={{ ...S.tabBtn, ...(insightTab === t.key ? S.tabBtnActive : {}) }}>
                    {t.label}
                  </button>
                ))}
              </div>

              {!result ? (
                <div style={S.placeholder}>Run a scenario to see insights.</div>
              ) : aiLoading ? (
                <><Shimmer mt={8} /><Shimmer w="85%" mt={8} h={14} /><Shimmer w="70%" mt={8} h={14} /></>
              ) : insightTab === 'changes' && !aiNarrative ? (
                <div style={S.placeholder}>AI narrative is loading — try again in a moment.</div>
              ) : (
                <ul style={S.list}>
                  {insightItems.map((item, i) => (
                    <li key={i} style={S.listItem}>{item}</li>
                  ))}
                  {insightItems.length === 0 && (
                    <li style={{ ...S.listItem, color: '#94a3b8', listStyle: 'none' }}>
                      No items to show for this scenario.
                    </li>
                  )}
                </ul>
              )}
            </div>

            {/* ── Chat ──────────────────────────────────────────────────────── */}
            {result && (
              <div style={S.card}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                  <div style={S.eyebrow}>Ask about this scenario</div>
                  <span style={S.aiBadge}>✦ AI</span>
                </div>
                {chatMsgs.length > 0 && (
                  <div style={S.chatHistory}>
                    {chatMsgs.map((msg, i) => (
                      <div key={i} style={{
                        ...S.chatBubble,
                        ...(msg.role === 'user' ? S.chatUser : S.chatAI),
                      }}>
                        {msg.content}
                      </div>
                    ))}
                    {chatLoading && (
                      <div style={{ ...S.chatBubble, ...S.chatAI }}>
                        <span style={{ color: '#94a3b8', letterSpacing: 3, fontSize: 16 }}>●●●</span>
                      </div>
                    )}
                  </div>
                )}
                <form onSubmit={sendChat} style={S.chatForm}>
                  <input type="text" value={chatInput}
                    onChange={e => setChatInput(e.target.value)}
                    placeholder="e.g. What would it take to get to GO? How does BVLOS affect the economics?"
                    style={S.chatInput} disabled={chatLoading} />
                  <button type="submit"
                    disabled={!chatInput.trim() || chatLoading}
                    style={{ ...S.chatSend, opacity: (!chatInput.trim() || chatLoading) ? 0.5 : 1 }}>
                    Send
                  </button>
                </form>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function BenchmarkRow({ label, value, benchmark, reading, source }) {
  const isGood = reading?.toLowerCase().includes('within') || reading?.toLowerCase().includes('above') || reading?.toLowerCase().includes('compet')
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '10px 0',
      borderBottom: '1px solid #f1f5f9' }}>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#0f172a', marginBottom: 2 }}>{label}</div>
        <div style={{ fontSize: 12, color: '#64748b' }}>
          {value} · Ref: {benchmark}
        </div>
        {source && <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>Source: {source}</div>}
      </div>
      <span style={{
        display: 'inline-block', padding: '3px 9px', borderRadius: 999, fontSize: 11, fontWeight: 700,
        whiteSpace: 'nowrap', marginTop: 2,
        background: isGood ? '#dcfce7' : '#fee2e2',
        color: isGood ? '#166534' : '#991b1b',
      }}>
        {reading}
      </span>
    </div>
  )
}

function DetailSection({ title, rows }) {
  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase',
        letterSpacing: '0.07em', marginBottom: 8 }}>{title}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {rows.map(([k, v]) => (
          <div key={k} style={{ display: 'flex', gap: 12, fontSize: 13 }}>
            <div style={{ minWidth: 160, color: '#64748b', flexShrink: 0 }}>{k}</div>
            <div style={{ color: '#0f172a', fontWeight: 500, lineHeight: 1.5 }}>{v}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────

const S = {
  page: {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #edf4ff 0%, #f8fbff 45%, #ffffff 100%)',
    fontFamily: 'Inter, -apple-system, Arial, sans-serif',
    color: '#0f172a',
  },
  container: { maxWidth: 1320, margin: '0 auto', padding: '24px 24px 56px' },
  disclaimer: {
    background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: 14,
    padding: '12px 18px', marginBottom: 20, fontSize: 13, color: '#78350f',
    lineHeight: 1.5, display: 'flex', alignItems: 'flex-start', gap: 12,
  },
  disclaimerBadge: {
    background: '#f59e0b', color: 'white', borderRadius: 6, padding: '3px 8px',
    fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em',
    whiteSpace: 'nowrap', marginTop: 1,
  },
  hero: { marginBottom: 28 },
  title: {
    fontSize: 48, lineHeight: 1, margin: '0 0 14px', letterSpacing: -1.5,
    color: '#0f172a', textAlign: 'center',
  },
  subtitle: {
    fontSize: 17, maxWidth: 680, lineHeight: 1.65, color: '#475569',
    margin: '0 auto', textAlign: 'center',
  },
  grid: { display: 'grid', gridTemplateColumns: '400px minmax(0,1fr)', gap: 24, alignItems: 'start' },
  left:  { display: 'flex', flexDirection: 'column', gap: 20, minWidth: 0 },
  right: { display: 'flex', flexDirection: 'column', gap: 20, minWidth: 0 },
  card: {
    background: 'rgba(255,255,255,0.84)', borderRadius: 20, padding: 24,
    border: '1px solid rgba(226,232,240,0.85)',
    boxShadow: '0 12px 40px rgba(15,23,42,0.07)', minWidth: 0, overflow: 'hidden',
  },
  eyebrow: {
    fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em',
    color: '#64748b', marginBottom: 8, fontWeight: 700,
  },
  sectionTitle: { margin: 0, fontSize: 22, letterSpacing: -0.4, color: '#0f172a' },
  headline: { margin: '0 0 4px', fontSize: 22, letterSpacing: -0.4, color: '#0f172a', lineHeight: 1.3 },
  subtext: { margin: 0, color: '#475569', lineHeight: 1.65, fontSize: 14 },
  blockTitle: { margin: '0 0 14px', fontSize: 18, letterSpacing: -0.3, color: '#0f172a' },
  label: {
    display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6,
    marginBottom: 6, fontWeight: 700, fontSize: 14, color: '#1e293b',
  },
  unitBadge: {
    background: '#f1f5f9', color: '#64748b', borderRadius: 6,
    padding: '2px 7px', fontSize: 11, fontWeight: 600,
  },
  valueBadge: {
    background: '#dbeafe', color: '#1d4ed8', borderRadius: 6,
    padding: '2px 7px', fontSize: 11, fontWeight: 700,
  },
  input: {
    width: '100%', padding: '11px 14px', borderRadius: 12,
    border: '1px solid #cbd5e1', fontSize: 14, background: '#ffffff',
    color: '#0f172a', boxSizing: 'border-box',
  },
  infoBox: {
    background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 10,
    padding: '8px 12px', fontSize: 12, color: '#0369a1', lineHeight: 1.5,
  },
  slider: { width: '100%', marginTop: 4, accentColor: '#0b1736' },
  sliderTicks: { display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94a3b8', marginTop: 2 },
  hint: { margin: '5px 0 0', fontSize: 12, color: '#94a3b8', lineHeight: 1.5 },
  button: {
    marginTop: 22, width: '100%', padding: 14, borderRadius: 14, border: 'none',
    background: 'linear-gradient(135deg, #0b1736 0%, #10204b 100%)',
    color: 'white', fontSize: 15, fontWeight: 700, cursor: 'pointer',
    boxShadow: '0 8px 24px rgba(11,23,54,0.22)',
  },
  error: { color: '#dc2626', marginTop: 12, fontWeight: 600, fontSize: 13, lineHeight: 1.5 },
  tabRow: { display: 'flex', gap: 8, flexWrap: 'wrap' },
  tabBtn: {
    padding: '9px 14px', borderRadius: 999, border: '1px solid #cbd5e1',
    background: '#ffffff', color: '#475569', fontSize: 13, fontWeight: 700, cursor: 'pointer',
  },
  tabBtnActive: { background: '#0b1736', color: 'white', border: '1px solid #0b1736' },
  kpiGrid: { display: 'grid', gridTemplateColumns: 'repeat(2,minmax(0,1fr))', gap: 14 },
  kpiCard: {
    background: 'rgba(255,255,255,0.9)', padding: 18, borderRadius: 18,
    border: '1px solid rgba(226,232,240,0.9)', boxSizing: 'border-box',
    minWidth: 0, textAlign: 'center',
  },
  kpiLabel: {
    fontSize: 11, color: '#64748b', marginBottom: 10, fontWeight: 700,
    textTransform: 'uppercase', letterSpacing: '0.05em', lineHeight: 1.4,
  },
  kpiValueRow: {
    display: 'flex', alignItems: 'baseline', justifyContent: 'center',
    gap: 5, marginBottom: 6, flexWrap: 'wrap',
  },
  kpiValue:  { fontSize: 26, fontWeight: 800, color: '#0f172a', lineHeight: 1 },
  kpiUnit:   { fontSize: 12, color: '#64748b', fontWeight: 500 },
  kpiSub:    { fontSize: 12, color: '#64748b', lineHeight: 1.4, textAlign: 'center' },
  placeholder: {
    minHeight: 100, display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#94a3b8', background: '#f8fafc', borderRadius: 14, textAlign: 'center',
    padding: 20, fontSize: 14,
  },
  th: {
    textAlign: 'left', padding: '9px 10px', borderBottom: '1px solid #e2e8f0',
    color: '#64748b', fontSize: 11, textTransform: 'uppercase',
    letterSpacing: '0.06em', fontWeight: 700,
  },
  td: {
    padding: '11px 10px', borderBottom: '1px solid #f1f5f9',
    color: '#334155', verticalAlign: 'top', fontSize: 13,
  },
  list: { margin: 0, paddingLeft: 20, color: '#475569' },
  listItem: { marginBottom: 12, lineHeight: 1.65, fontSize: 14 },
  aiBadge: {
    display: 'inline-block',
    background: 'linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%)',
    color: 'white', fontSize: 10, fontWeight: 700, padding: '2px 7px',
    borderRadius: 6, letterSpacing: '0.05em',
  },
  chatHistory: {
    display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 14,
    maxHeight: 320, overflowY: 'auto', padding: '4px 0',
  },
  chatBubble: { padding: '10px 14px', borderRadius: 14, fontSize: 14, lineHeight: 1.6, maxWidth: '90%' },
  chatUser: { background: '#0b1736', color: 'white', alignSelf: 'flex-end', borderBottomRightRadius: 4 },
  chatAI:   { background: '#f1f5f9', color: '#0f172a', alignSelf: 'flex-start', borderBottomLeftRadius: 4 },
  chatForm: { display: 'flex', gap: 10, alignItems: 'center' },
  chatInput: {
    flex: 1, padding: '10px 14px', borderRadius: 12, border: '1px solid #cbd5e1',
    fontSize: 14, background: '#ffffff', color: '#0f172a', outline: 'none',
  },
  chatSend: {
    padding: '10px 18px', borderRadius: 12, border: 'none',
    background: 'linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%)',
    color: 'white', fontSize: 14, fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap',
  },
}
