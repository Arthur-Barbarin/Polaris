import { VEHICLES } from '../data/vehicles.js'

const VEHICLE_ORDER = ['joby_s4', 'archer_midnight', 'wisk_gen6', 'custom']

function SliderField({ label, unit, value, min, max, step = 1, onChange, hint }) {
  return (
    <div className="field">
      <label>
        {label}
        <span>{unit}</span>
      </label>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
      />
      <div className="field-value">{value.toLocaleString()} {unit}</div>
      {hint && <div className="note">{hint}</div>}
    </div>
  )
}

export default function VehicleSelector({ vehicleId, setVehicleId, customVehicle, setCustomVehicle }) {
  const v = VEHICLES[vehicleId] || customVehicle

  const updateCustom = (key, val) =>
    setCustomVehicle(prev => ({ ...prev, [key]: val }))

  return (
    <div className="panel">
      <div className="panel-title">Vehicle</div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 18 }}>
        {VEHICLE_ORDER.map(id => {
          const veh = VEHICLES[id]
          const active = vehicleId === id
          return (
            <button
              key={id}
              onClick={() => setVehicleId(id)}
              style={{
                background: active ? `${veh.color}18` : '#0f1420',
                border: `1px solid ${active ? veh.color : '#252d40'}`,
                borderRadius: 8,
                padding: '10px 12px',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: active ? veh.color : '#c8d0e8' }}>
                  {veh.name}
                </span>
                {id !== 'custom' && (
                  <span style={{ fontSize: 10, color: '#5a6080' }}>
                    {veh.seats_passenger}p · {veh.range_km}km
                  </span>
                )}
              </div>
              {id !== 'custom' && (
                <div style={{ fontSize: 11, color: '#5a6080', marginTop: 2 }}>
                  {veh.manufacturer} · {veh.piloted ? 'Piloted' : 'Autonomous'}
                </div>
              )}
            </button>
          )
        })}
      </div>

      {vehicleId !== 'custom' && (
        <div style={{ background: '#0f1420', borderRadius: 8, padding: '12px 14px', fontSize: 12 }}>
          <div style={{ color: '#5a6080', marginBottom: 8 }}>{v.notes}</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            {[
              ['Battery', `${v.battery_kwh} kWh`],
              ['Cruise', `${v.cruise_speed_kmh} km/h`],
              ['Charge', `${v.charge_time_min} min`],
              ['List price', `$${(v.aircraft_cost_usd / 1e6).toFixed(1)}M`],
            ].map(([k, val]) => (
              <div key={k}>
                <div style={{ fontSize: 10, color: '#3a4060', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{k}</div>
                <div style={{ fontSize: 12, color: '#c8d0e8', fontWeight: 600 }}>{val}</div>
              </div>
            ))}
          </div>
          <div className="source-line" style={{ marginTop: 10 }}>{v.status}</div>
        </div>
      )}

      {vehicleId === 'custom' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <SliderField label="Passenger seats" unit="seats" value={customVehicle.seats_passenger}
            min={1} max={8} onChange={v => updateCustom('seats_passenger', v)} />
          <SliderField label="Range" unit="km" value={customVehicle.range_km}
            min={20} max={400} step={5} onChange={v => updateCustom('range_km', v)} />
          <SliderField label="Cruise speed" unit="km/h" value={customVehicle.cruise_speed_kmh}
            min={80} max={400} step={5} onChange={v => updateCustom('cruise_speed_kmh', v)} />
          <SliderField label="Energy intensity" unit="kWh/seat-km" value={customVehicle.kWh_per_seat_km}
            min={0.05} max={0.8} step={0.01} onChange={v => updateCustom('kWh_per_seat_km', v)} />
          <SliderField label="Charge time" unit="min" value={customVehicle.charge_time_min}
            min={5} max={60} onChange={v => updateCustom('charge_time_min', v)} />
          <SliderField label="Aircraft cost" unit="$M" value={customVehicle.aircraft_cost_usd / 1e6}
            min={0.5} max={10} step={0.1} onChange={v => updateCustom('aircraft_cost_usd', v * 1e6)} />
          <SliderField label="Maintenance" unit="$/FH" value={customVehicle.maintenance_per_fh_usd}
            min={50} max={500} step={5} onChange={v => updateCustom('maintenance_per_fh_usd', v)} />
          <div className="field">
            <label>Piloted</label>
            <label style={{ flexDirection: 'row', gap: 8, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={customVehicle.piloted}
                onChange={e => updateCustom('piloted', e.target.checked)}
                style={{ accentColor: '#4A90D9', cursor: 'pointer' }}
              />
              <span style={{ fontSize: 12, color: '#9aa0b8' }}>Requires pilot</span>
            </label>
          </div>
        </div>
      )}
    </div>
  )
}
