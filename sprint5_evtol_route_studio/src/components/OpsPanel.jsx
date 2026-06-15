import { useState } from 'react';
import { fmt_usd } from '../models/economics.js';

function Slider({ label, hint, unit, value, min, max, step = 1, onChange, displayFn, disabled }) {
  const display = displayFn ? displayFn(value) : `${value} ${unit}`;
  return (
    <div className="field" style={{ opacity: disabled ? 0.4 : 1 }}>
      <label>
        {label}
        {hint && <span style={{ fontSize: 10, color: '#3a4060', fontStyle: 'italic', maxWidth: 120, textAlign: 'right', lineHeight: 1.3 }}>{hint}</span>}
      </label>
      <input type="range" min={min} max={max} step={step} value={value} disabled={disabled}
        onChange={e => onChange(Number(e.target.value))} />
      <div className="field-value">{display}</div>
    </div>
  );
}

export default function OpsPanel({ ops, setOps, vehicle }) {
  const [open, setOpen] = useState(false);
  const set = (key, val) => setOps(prev => ({ ...prev, [key]: val }));

  return (
    <div className="panel" style={{ padding: 0 }}>
      {/* Collapsible header */}
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', background: 'none', border: 'none', cursor: 'pointer',
          padding: '14px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}
      >
        <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.8px', textTransform: 'uppercase', color: '#4A90D9' }}>
          Operations
        </span>
        <span style={{ fontSize: 12, color: '#5a6080' }}>{open ? '▲ collapse' : '▼ expand'}</span>
      </button>

      {open && (
        <div style={{ padding: '0 18px 18px' }}>
          <Slider label="Electricity price" unit="$/kWh" value={ops.electricity_price_usd_kwh}
            min={0.05} max={0.50} step={0.01} onChange={v => set('electricity_price_usd_kwh', v)}
            displayFn={v => `$${v.toFixed(2)}/kWh`}
            hint="EIA avg $0.14" />

          <Slider label="Pilot cost" unit="$/FH" value={ops.pilot_cost_per_fh_usd}
            min={40} max={300} step={5} onChange={v => set('pilot_cost_per_fh_usd', v)}
            displayFn={v => fmt_usd(v, 0) + '/FH'}
            disabled={!vehicle.piloted}
            hint={vehicle.piloted ? 'ATP loaded' : 'Auto — see remote ops'} />

          <Slider label="Landing fee" unit="$/landing" value={ops.landing_fee_usd}
            min={0} max={300} step={5} onChange={v => set('landing_fee_usd', v)}
            displayFn={v => fmt_usd(v, 0)}
            hint="Vertiport est." />

          <Slider label="Turnaround time" unit="min" value={ops.turnaround_time_min}
            min={5} max={60} onChange={v => set('turnaround_time_min', v)}
            hint="Max ground time" />

          <Slider label="Aircraft availability" unit="" value={ops.availability_factor}
            min={0.5} max={0.99} step={0.01} onChange={v => set('availability_factor', v)}
            displayFn={v => `${Math.round(v * 100)}%`}
            hint="Incl. MX, weather" />

          <Slider label="Energy reserve" unit="" value={ops.energy_reserve_pct}
            min={0.10} max={0.40} step={0.01} onChange={v => set('energy_reserve_pct', v)}
            displayFn={v => `${Math.round(v * 100)}%`}
            hint="FAA-style 20% min" />

          <Slider label="Deadhead rate" unit="" value={ops.deadhead_factor}
            min={0.0} max={0.40} step={0.01} onChange={v => set('deadhead_factor', v)}
            displayFn={v => `${Math.round(v * 100)}%`}
            hint="Empty repositioning" />

          <Slider label="Infra capex / aircraft" unit="$k" value={ops.infrastructure_capex_per_aircraft / 1000}
            min={50} max={1000} step={25} onChange={v => set('infrastructure_capex_per_aircraft', v * 1000)}
            displayFn={v => `$${v}k`}
            hint="Vertiport share" />
        </div>
      )}
    </div>
  );
}
