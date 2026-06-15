import { useState, useMemo } from 'react'
import { VEHICLES, DEFAULT_ROUTE, DEFAULT_OPERATIONS } from './data/vehicles.js'
import {
  computeEconomics,
  computeBreakevenCurve,
  computeSensitivity,
  computeBindingConstraint,
} from './models/economics.js'
import VehicleSelector from './components/VehicleSelector.jsx'
import RoutePanel from './components/RoutePanel.jsx'
import OpsPanel from './components/OpsPanel.jsx'
import MetricsBar from './components/MetricsBar.jsx'
import InsightCard from './components/InsightCard.jsx'
import BreakevenChart from './components/BreakevenChart.jsx'
import WaterfallChart from './components/WaterfallChart.jsx'
import SensitivityChart from './components/SensitivityChart.jsx'
import CasmChart from './components/CasmChart.jsx'
import VehicleComparison from './components/VehicleComparison.jsx'

const STYLES = `
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0a0d14;
    color: #e8eaf0;
    min-height: 100vh;
  }
  .app { max-width: 1440px; margin: 0 auto; padding: 24px 20px; }

  .header { margin-bottom: 24px; }
  .header-top { display: flex; align-items: center; gap: 14px; margin-bottom: 6px; flex-wrap: wrap; }
  .header h1 { font-size: 20px; font-weight: 700; letter-spacing: -0.3px; color: #fff; }
  .sprint-tag {
    font-size: 10px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase;
    color: #4A90D9; border: 1px solid #4A90D9; border-radius: 4px; padding: 2px 8px;
    flex-shrink: 0;
  }
  .header p { font-size: 12px; color: #7a8099; line-height: 1.5; }

  .layout { display: grid; grid-template-columns: 300px 1fr; gap: 20px; }
  @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }

  .sidebar { display: flex; flex-direction: column; gap: 14px; }
  .main { display: flex; flex-direction: column; gap: 18px; }

  .panel {
    background: #131720;
    border: 1px solid #1e2535;
    border-radius: 10px;
    padding: 16px;
  }
  .panel-title {
    font-size: 10px; font-weight: 600; letter-spacing: 0.8px;
    text-transform: uppercase; color: #4A90D9; margin-bottom: 14px;
  }

  .field { margin-bottom: 12px; }
  .field:last-child { margin-bottom: 0; }
  .field label {
    display: flex; justify-content: space-between; align-items: flex-start;
    font-size: 12px; color: #9aa0b8; margin-bottom: 4px; gap: 8px;
  }
  .field label span { font-size: 10px; color: #5a6080; flex-shrink: 0; }
  .field input[type=range] { width: 100%; accent-color: #4A90D9; cursor: pointer; height: 16px; }
  .field-value { font-size: 12px; font-weight: 600; color: #c8d0e8; margin-top: 1px; }

  .metrics-grid {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
  }
  @media (max-width: 1100px) { .metrics-grid { grid-template-columns: repeat(2, 1fr); } }

  .metric-card {
    background: #0f1420; border: 1px solid #1e2535; border-radius: 8px; padding: 14px 16px;
  }
  .metric-label { font-size: 10px; color: '#5a6080'; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; color: #5a6080; }
  .metric-value { font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
  .metric-sub { font-size: 11px; color: #5a6080; margin-top: 2px; }
  .metric-positive { color: #2DBD7E; }
  .metric-negative { color: #E85C5C; }
  .metric-neutral { color: #e8eaf0; }
  .metric-warn { color: #E8813A; }

  .chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
  @media (max-width: 1100px) { .chart-row { grid-template-columns: 1fr; } }

  .alert-banner {
    background: #2a1a0a; border: 1px solid #E8813A; border-radius: 8px;
    padding: 10px 14px; font-size: 12px; color: #E8813A;
  }

  .chart-title { font-size: 13px; font-weight: 600; color: #c8d0e8; margin-bottom: 3px; }
  .chart-sub { font-size: 11px; color: #5a6080; margin-bottom: 14px; line-height: 1.4; }

  .source-line { font-size: 10px; color: '#3a4060'; margin-top: 10px; font-style: italic; color: #3a4060; }

  .divider { border: none; border-top: 1px solid #1e2535; }
  .note { font-size: 11px; color: #5a6080; line-height: 1.5; margin-top: 6px; }

  .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #1e2535;
    font-size: 10px; color: #3a4060; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
`

export default function App() {
  const [vehicleId, setVehicleId] = useState('joby_s4')
  const [customVehicle, setCustomVehicle] = useState({ ...VEHICLES.custom })
  const [route, setRoute] = useState({ ...DEFAULT_ROUTE })
  const [ops, setOps] = useState({ ...DEFAULT_OPERATIONS })

  const vehicle = vehicleId === 'custom' ? customVehicle : VEHICLES[vehicleId]

  const result = useMemo(() => computeEconomics(vehicle, route, ops), [vehicle, route, ops])
  const breakevenCurve = useMemo(() => computeBreakevenCurve(vehicle, route, ops), [vehicle, route, ops])
  const sensitivity = useMemo(() => computeSensitivity(vehicle, route, ops), [vehicle, route, ops])
  const constraint = useMemo(() => computeBindingConstraint(result, vehicle), [result, vehicle])

  return (
    <>
      <style>{STYLES}</style>
      <div className="app">
        <header className="header">
          <div className="header-top">
            <span className="sprint-tag">Sprint 5</span>
            <h1>eVTOL Route Viability Studio</h1>
          </div>
          <p>Unit economics for urban air mobility — models CASM, break-even utilization, P&L, and input leverage. Includes energy reserve, deadhead, and cycle-driven maintenance. Not a regulatory compliance tool.</p>
        </header>

        <div className="layout">
          <aside className="sidebar">
            <VehicleSelector
              vehicleId={vehicleId}
              setVehicleId={setVehicleId}
              customVehicle={customVehicle}
              setCustomVehicle={setCustomVehicle}
            />
            <RoutePanel route={route} setRoute={setRoute} result={result} />
            <OpsPanel ops={ops} setOps={setOps} vehicle={vehicle} />
          </aside>

          <main className="main">
            {/* 1. Binding constraint card — first thing investor sees */}
            <InsightCard constraint={constraint} result={result} />

            {/* 2. Key metrics */}
            <MetricsBar result={result} />

            {/* 3. Break-even curve + waterfall */}
            <div className="chart-row">
              <BreakevenChart
                curve={breakevenCurve}
                currentLF={route.load_factor}
                breakevenLF={result.breakeven_load_factor}
                vehicle={vehicle}
              />
              <WaterfallChart result={result} />
            </div>

            {/* 4. Leverage + CASM */}
            <div className="chart-row">
              <SensitivityChart sensitivity={sensitivity} />
              <CasmChart result={result} vehicle={vehicle} />
            </div>

            {/* 5. Cross-vehicle comparison at current route/ops */}
            <VehicleComparison route={route} ops={ops} activeVehicleId={vehicleId} />
          </main>
        </div>

        <footer className="footer">
          <span>Polaris Decision Modeling Studio — Sprint 5</span>
          <span>Sources: Joby/Archer SEC filings · NREL 2023 · NASA UAM Market Study · EIA · BLS · FAA · Not a certified financial model</span>
        </footer>
      </div>
    </>
  )
}
