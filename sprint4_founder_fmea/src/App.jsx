import { useState, useMemo, useEffect, useCallback } from 'react'
import FaultTree from './components/FaultTree.jsx'
import InputPanel from './components/InputPanel.jsx'
import ScenarioComparison from './components/ScenarioComparison.jsx'
import RiskTrajectory from './components/RiskTrajectory.jsx'
import { SurvivalScore, RiskDecomposition, BindingConstraint, SensitivityRanking } from './components/OutputPanels.jsx'
import {
  DEFAULT_INPUTS,
  computeLeafProbabilities,
  propagateTree,
  runMonteCarlo,
  computeSensitivity,
  computeRiskDecomposition,
  computeResilienceScore,
  findBindingConstraint,
  computeTrajectory,
} from './engine/faultTree.js'

// Debounce for MC (expensive)
function useDebounce(value, delay) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}

export default function App() {
  const [inputs, setInputs] = useState(DEFAULT_INPUTS)
  const [mcResult, setMcResult] = useState(null)
  const [mcRunning, setMcRunning] = useState(false)
  const [baseline, setBaseline] = useState(null)
  const [activeTab, setActiveTab] = useState('analysis')  // 'analysis' | 'trajectory'
  const debouncedInputs = useDebounce(inputs, 300)

  // Live deterministic results (instant)
  const leaves      = useMemo(() => computeLeafProbabilities(inputs), [inputs])
  const branchProbs = useMemo(() => propagateTree(leaves), [leaves])
  const resilience  = useMemo(() => computeResilienceScore(branchProbs), [branchProbs])
  const decomp      = useMemo(() => computeRiskDecomposition(branchProbs), [branchProbs])
  const binding     = useMemo(() => findBindingConstraint(leaves), [leaves])
  const sensitivity = useMemo(() => computeSensitivity(inputs), [inputs])

  const trajectory = useMemo(() => computeTrajectory(inputs, 18), [inputs])

  const saveBaseline = () => setBaseline({ inputs: { ...inputs }, leaves: { ...leaves }, branchProbs: { ...branchProbs }, resilience })
  const clearBaseline = () => setBaseline(null)

  // Monte Carlo on debounced inputs
  useEffect(() => {
    setMcRunning(true)
    const t = setTimeout(() => {
      const result = runMonteCarlo(debouncedInputs, 10000)
      setMcResult(result)
      setMcRunning(false)
    }, 0)
    return () => clearTimeout(t)
  }, [debouncedInputs])

  // Run once on mount
  useEffect(() => {
    const result = runMonteCarlo(DEFAULT_INPUTS, 10000)
    setMcResult(result)
  }, [])

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>

      {/* Header */}
      <header style={{
        borderBottom: '1px solid var(--border)',
        padding: '14px 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'var(--surface)',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: 'linear-gradient(135deg, #6366f1, #818cf8)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16, fontWeight: 700, color: '#fff',
          }}>◈</div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)' }}>
              Founder Failure Mode Analyzer
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                Aerospace-grade failure analysis
              </span>
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: '0.06em',
                padding: '1px 7px', borderRadius: 4,
                background: '#6366f122', border: '1px solid #6366f155',
                color: '#818cf8',
              }}>
                B2B SaaS · Seed Stage
              </span>
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {mcRunning && (
            <span style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--mono)' }}>
              ⟳ running MC…
            </span>
          )}
          <span style={{
            fontSize: 11, color: '#64748b',
            padding: '3px 10px',
            border: '1px solid var(--border)',
            borderRadius: 6,
            fontFamily: 'var(--mono)',
          }}>
            Polaris · Sprint 4
          </span>
        </div>
      </header>

      {/* Tagline */}
      <div style={{
        background: 'linear-gradient(135deg, #0f1220 0%, #111520 100%)',
        borderBottom: '1px solid var(--border)',
        padding: '18px 32px 16px',
        textAlign: 'center',
      }}>
        <p style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.6, marginBottom: 12, maxWidth: 680, margin: '0 auto 12px' }}>
          <span style={{ color: '#818cf8', fontWeight: 600 }}>What if startups were analyzed the same way aerospace engineers analyze aircraft failures?</span>
          {' '}FMEA + fault tree methodology from a field where failure is unacceptable.
        </p>
        {/* 3-step how to use — inline, centered */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, flexWrap: 'wrap' }}>
          {[
            '① Enter approximate inputs',
            '② Save a baseline',
            '③ Adjust sliders to compare',
          ].map((step, i) => (
            <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{
                fontSize: 11, color: '#64748b',
                padding: '3px 10px', borderRadius: 20,
                border: '1px solid #1e293b', background: '#0d1117',
              }}>{step}</span>
              {i < 2 && <span style={{ color: '#1e293b', fontSize: 12 }}>→</span>}
            </span>
          ))}
          <span style={{ fontSize: 11, color: '#334155', marginLeft: 8 }}>·</span>
          <span style={{ fontSize: 11, color: '#475569', fontStyle: 'italic' }}>the delta between scenarios is the insight</span>
        </div>
      </div>

      {/* Main layout */}
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '24px 32px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 24, alignItems: 'start' }}>

          {/* Left — Inputs */}
          <div style={{ position: 'sticky', top: 73, maxHeight: 'calc(100vh - 100px)', overflowY: 'auto', paddingRight: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>
                Startup Parameters
              </span>
              {baseline ? (
                <button onClick={clearBaseline} style={{
                  padding: '3px 10px', borderRadius: 5, cursor: 'pointer',
                  background: '#22c55e22', border: '1px solid #22c55e55',
                  color: '#22c55e', fontSize: 10, fontWeight: 700,
                  fontFamily: 'var(--font)', letterSpacing: '0.04em',
                }}>
                  ✕ Clear Baseline
                </button>
              ) : (
                <button onClick={saveBaseline} style={{
                  padding: '3px 10px', borderRadius: 5, cursor: 'pointer',
                  background: '#6366f122', border: '1px solid #6366f155',
                  color: '#818cf8', fontSize: 10, fontWeight: 700,
                  fontFamily: 'var(--font)', letterSpacing: '0.04em',
                }}>
                  ⊕ Save Baseline
                </button>
              )}
            </div>
            {baseline && (
              <div style={{
                fontSize: 11, color: '#22c55e', marginBottom: 10,
                padding: '5px 10px', borderRadius: 6,
                background: '#22c55e0d', border: '1px solid #22c55e33',
              }}>
                Baseline saved · adjust inputs to compare
              </div>
            )}
            <InputPanel inputs={inputs} onChange={setInputs} />
            <button
              onClick={() => { setInputs(DEFAULT_INPUTS); clearBaseline() }}
              style={{
                width: '100%', marginTop: 8, padding: '8px',
                background: 'var(--surface2)', border: '1px solid var(--border)',
                borderRadius: 8, color: 'var(--muted)', fontSize: 12,
                cursor: 'pointer', fontFamily: 'var(--font)',
              }}
            >
              Reset to Defaults
            </button>
          </div>

          {/* Right — tabbed output */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* Tab switcher */}
            <div style={{ display: 'flex', gap: 4 }}>
              {[
                { id: 'analysis',    label: 'Failure Analysis' },
                { id: 'trajectory',  label: 'Risk Trajectory' },
              ].map(tab => (
                <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
                  padding: '7px 18px', borderRadius: 7, cursor: 'pointer',
                  background: activeTab === tab.id ? '#6366f1' : 'var(--surface2)',
                  border: `1px solid ${activeTab === tab.id ? '#6366f1' : 'var(--border)'}`,
                  color: activeTab === tab.id ? '#fff' : '#64748b',
                  fontSize: 12, fontWeight: activeTab === tab.id ? 600 : 400,
                  fontFamily: 'var(--font)', transition: 'all 0.15s',
                }}>
                  {tab.label}
                </button>
              ))}
            </div>

            {/* ── Failure Analysis tab ─────────────────────── */}
            {activeTab === 'analysis' && <>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <SurvivalScore resilience={resilience} mcResilience={mcResult?.resilience} mcRunning={mcRunning} />
                <RiskDecomposition decomp={decomp} branchProbs={branchProbs} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <BindingConstraint constraint={binding} />
                <SensitivityRanking sensitivity={sensitivity} />
              </div>
              <ScenarioComparison
                baseline={baseline}
                current={{ inputs, leaves, branchProbs, resilience }}
              />
            </>}

            {/* ── Risk Trajectory tab ──────────────────────── */}
            {activeTab === 'trajectory' && (
              <RiskTrajectory trajectory={trajectory} baseInputs={inputs} />
            )}
          </div>
        </div>

        {/* Fault tree — full page width so nodes render large enough to read */}
        <div style={{ marginTop: 8 }}>
          <FaultTree leaves={leaves} branchProbs={branchProbs} />
        </div>
      </div>

      {/* Methodology footer */}
      <div style={{
        borderTop: '1px solid var(--border)',
        padding: '14px 32px',
        background: '#0a0c10',
        fontSize: 11, color: '#475569', lineHeight: 1.8,
        display: 'flex', gap: 32, flexWrap: 'wrap',
      }}>
        <div style={{ flex: 1, minWidth: 280 }}>
          <span style={{ color: '#64748b', fontWeight: 600 }}>Fault Tree: </span>
          IEC 61025 + MIL-STD-1629A. OR-gate propagation: P(branch) = 1 − ∏(1 − P(leaf)). Used for failure mode visualization only.
        </div>
        <div style={{ flex: 1, minWidth: 280 }}>
          <span style={{ color: '#64748b', fontWeight: 600 }}>Resilience Index: </span>
          Weighted average — Capital 30%, Revenue 30%, Team 20%, Product 20%. Calibrated against B2B SaaS Series A benchmarks. Structured reasoning aid, not a statistical prediction.
        </div>
      </div>
    </div>
  )
}
