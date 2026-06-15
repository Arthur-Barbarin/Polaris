/**
 * eVTOL Route Economics Engine — Sprint 5, Polaris
 *
 * Model fixes vs v1:
 *  1. Energy reserve: FAA-style 20% reserve → actual mission energy = kwh / (1 - reserve_pct)
 *  2. Deadhead factor: ~15% of flights reposition empty → revenue only on (1 - deadhead) flights
 *  3. Autonomous crew: Wisk uses remote_ops_cost_per_fh (not $0 — FAA requires remote pilot oversight)
 *  4. Cycle maintenance: per-cycle cost added alongside per-FH cost (eVTOL wear is cycle-driven)
 *  5. Break-even LF: correctly accounts for deadhead (fewer revenue opportunities per period)
 *  6. RASM: computed on revenue flights only, not total flights
 *  7. Binding constraint: identifies primary reason for route status in plain language
 */

const KM_TO_MILES = 0.621371;

export function computeEconomics(vehicle, route, ops) {
  const { distance_km, fare_per_seat_usd, load_factor } = route;
  const {
    electricity_price_usd_kwh,
    pilot_cost_per_fh_usd,
    landing_fee_usd,
    infrastructure_capex_per_aircraft,
    availability_factor,
    turnaround_time_min,
    energy_reserve_pct,   // NEW: fraction of battery held as reserve (default 0.20)
    deadhead_factor,       // NEW: fraction of flights that are empty repositioning (default 0.15)
  } = ops;

  // --- Flight physics ---
  const flight_time_h = distance_km / vehicle.cruise_speed_kmh;
  const flight_time_min = flight_time_h * 60;

  // Ground time: max of minimum boarding time and charge time for energy used.
  // Energy used per flight as fraction of total battery:
  const mission_kwh_raw = vehicle.kWh_per_seat_km * distance_km * vehicle.seats_passenger;
  // Energy reserve: must retain (energy_reserve_pct) of battery. So we need to carry
  // enough that after using mission energy, reserve_pct remains.
  // effective_mission_kwh = mission_kwh_raw / (1 - reserve_pct)
  const energy_reserve_factor = 1 / (1 - energy_reserve_pct);
  const energy_kwh_with_reserve = mission_kwh_raw * energy_reserve_factor;
  // Fraction of battery actually consumed (net of reserve):
  const battery_fraction_used = mission_kwh_raw / vehicle.battery_kwh;
  // Proportional charge time (linear approximation at rapid-charge rate):
  const proportional_charge_min = battery_fraction_used * vehicle.charge_time_min;
  const ground_time_min = Math.max(vehicle.min_ground_time_min, proportional_charge_min);
  const cycle_time_min = flight_time_min + Math.min(turnaround_time_min, ground_time_min);

  // --- Per-flight costs ---
  // Energy: use energy WITH reserve to reflect actual operational energy budget
  const energy_cost = energy_kwh_with_reserve * electricity_price_usd_kwh;

  // Crew: pilot if piloted; remote operator if autonomous (autonomous ≠ free)
  const crew_cost = vehicle.piloted
    ? pilot_cost_per_fh_usd * flight_time_h
    : vehicle.remote_ops_cost_per_fh * flight_time_h;

  // Maintenance: hour-based + cycle-based (eVTOL wear is cycle-driven: battery replacements, rotor fatigue)
  const maintenance_cost = vehicle.maintenance_per_fh_usd * flight_time_h
    + vehicle.maintenance_per_cycle_usd; // one cycle = one landing

  const total_opex_per_flight = energy_cost + crew_cost + maintenance_cost + landing_fee_usd;

  // --- Per-flight revenue (paying passengers only) ---
  const revenue_per_flight_full = fare_per_seat_usd * vehicle.seats_passenger;
  const revenue_per_flight = revenue_per_flight_full * load_factor;
  const margin_per_flight = revenue_per_flight - total_opex_per_flight;

  // --- Annual utilization ---
  const operating_hours_per_day = 16;
  const flights_per_day = Math.floor((operating_hours_per_day * 60) / cycle_time_min);
  const annual_flights_total = Math.round(flights_per_day * 365 * availability_factor);
  // Revenue-generating flights: total minus deadhead repositioning flights
  const annual_flights_revenue = Math.round(annual_flights_total * (1 - deadhead_factor));

  // --- Annual economics ---
  // Opex applies to ALL flights (you burn energy and wear parts on deadhead too)
  const annual_opex = total_opex_per_flight * annual_flights_total;
  // Revenue only comes from paying-passenger flights
  const annual_revenue = revenue_per_flight * annual_flights_revenue;

  const annual_capex =
    vehicle.aircraft_cost_usd / vehicle.useful_life_years +
    infrastructure_capex_per_aircraft / vehicle.useful_life_years;

  const annual_profit = annual_revenue - annual_opex - annual_capex;
  const annual_margin_pct = annual_revenue > 0 ? annual_profit / annual_revenue : 0;

  // --- CASM / RASM (revenue flights only for RASM — deadhead generates no revenue) ---
  const distance_miles = distance_km * KM_TO_MILES;
  const available_seat_miles_total = vehicle.seats_passenger * annual_flights_total * distance_miles;
  const available_seat_miles_revenue = vehicle.seats_passenger * annual_flights_revenue * distance_miles;
  const casm = available_seat_miles_total > 0 ? annual_opex / available_seat_miles_total : 0;
  const rasm = available_seat_miles_revenue > 0 ? annual_revenue / available_seat_miles_revenue : 0;

  // --- Break-even load factor (accounting for deadhead) ---
  // annual_revenue(lf) = fare × seats × lf × revenue_flights
  // break-even: fare × seats × lf_be × revenue_flights = annual_opex + annual_capex
  const breakeven_load_factor = annual_flights_revenue > 0
    ? (annual_opex + annual_capex) / (revenue_per_flight_full * annual_flights_revenue)
    : Infinity;

  // Minimum fare to break even at current load factor
  const breakeven_fare_per_seat = annual_flights_revenue > 0 && load_factor > 0
    ? (annual_opex + annual_capex) / (annual_flights_revenue * vehicle.seats_passenger * load_factor)
    : 0;

  // --- Payback period ---
  const annual_net_operating = annual_revenue - annual_opex;
  const total_capex = vehicle.aircraft_cost_usd + infrastructure_capex_per_aircraft;
  const payback_years = annual_net_operating > 0 ? total_capex / annual_net_operating : Infinity;

  // --- Range feasibility ---
  const range_feasible = distance_km <= vehicle.max_range_segment_km;

  // --- Cost share breakdown (for binding constraint) ---
  const energy_share = total_opex_per_flight > 0 ? energy_cost / total_opex_per_flight : 0;
  const crew_share = total_opex_per_flight > 0 ? crew_cost / total_opex_per_flight : 0;
  const maintenance_share = total_opex_per_flight > 0 ? maintenance_cost / total_opex_per_flight : 0;
  const landing_share = total_opex_per_flight > 0 ? landing_fee_usd / total_opex_per_flight : 0;

  return {
    vehicle_id: vehicle.id,
    distance_km, distance_miles,
    fare_per_seat_usd, load_factor,

    flight_time_h, flight_time_min, cycle_time_min,
    flights_per_day,
    annual_flights: annual_flights_total,
    annual_flights_revenue,

    energy_kwh: energy_kwh_with_reserve,
    energy_kwh_raw: mission_kwh_raw,
    energy_cost,
    crew_cost,
    maintenance_cost,
    landing_fee: landing_fee_usd,
    total_opex_per_flight,
    revenue_per_flight,
    revenue_per_flight_full,
    margin_per_flight,

    annual_revenue,
    annual_opex,
    annual_capex,
    annual_profit,
    annual_margin_pct,

    casm, rasm,
    breakeven_load_factor,
    breakeven_fare_per_seat,
    payback_years,

    energy_share, crew_share, maintenance_share, landing_share,
    range_feasible,
    deadhead_factor,   // echo back so UI components don't need the ops object
  };
}

/**
 * Break-even curve: annual profit vs load factor (0–100%)
 */
export function computeBreakevenCurve(vehicle, route, ops) {
  const points = [];
  for (let lf = 0; lf <= 1.0; lf += 0.05) {
    const r = computeEconomics(vehicle, { ...route, load_factor: lf }, ops);
    points.push({
      load_factor_pct: Math.round(lf * 100),
      annual_profit: r.annual_profit,
    });
  }
  return points;
}

/**
 * Sensitivity tornado: impact on annual profit of ±20% change in each input.
 * Returns items sorted descending by absolute impact (highest leverage first).
 */
export function computeSensitivity(vehicle, route, ops) {
  const base = computeEconomics(vehicle, route, ops);
  const delta = 0.20;

  const inputs = [
    { key: 'fare_per_seat_usd',       label: 'Fare per seat',       type: 'route', direction: 'up_good' },
    { key: 'load_factor',             label: 'Load factor',         type: 'route', direction: 'up_good' },
    { key: 'deadhead_factor',         label: 'Deadhead rate',       type: 'ops',   direction: 'down_good' },
    { key: 'availability_factor',     label: 'Aircraft availability', type: 'ops', direction: 'up_good' },
    { key: 'electricity_price_usd_kwh', label: 'Electricity price', type: 'ops',  direction: 'down_good' },
    { key: 'pilot_cost_per_fh_usd',   label: 'Pilot cost/FH',      type: 'ops',   direction: 'down_good' },
    { key: 'landing_fee_usd',         label: 'Landing fee',         type: 'ops',   direction: 'down_good' },
    { key: 'turnaround_time_min',     label: 'Turnaround time',     type: 'ops',   direction: 'down_good' },
  ];

  return inputs.map(({ key, label, type, direction }) => {
    const upResult = type === 'route'
      ? computeEconomics(vehicle, { ...route, [key]: route[key] * (1 + delta) }, ops)
      : computeEconomics(vehicle, route, { ...ops, [key]: ops[key] * (1 + delta) });

    const downResult = type === 'route'
      ? computeEconomics(vehicle, { ...route, [key]: route[key] * (1 - delta) }, ops)
      : computeEconomics(vehicle, route, { ...ops, [key]: ops[key] * (1 - delta) });

    const impact_up = upResult.annual_profit - base.annual_profit;
    const impact_down = downResult.annual_profit - base.annual_profit;

    return {
      key, label, direction,
      impact_up,
      impact_down,
      abs_impact: Math.max(Math.abs(impact_up), Math.abs(impact_down)),
    };
  }).sort((a, b) => b.abs_impact - a.abs_impact);
}

/**
 * True waterfall data for P&L.
 * Each item has `base` (invisible stack bottom) and `bar` (visible amount).
 */
export function computeWaterfall(result) {
  const rev = result.annual_revenue;
  const energy_total = result.energy_cost * result.annual_flights;
  const crew_total = result.crew_cost * result.annual_flights;
  const maint_total = result.maintenance_cost * result.annual_flights;
  const land_total = result.landing_fee * result.annual_flights;
  const capex = result.annual_capex;
  const profit = result.annual_profit;

  let running = rev;
  const items = [];

  const push = (name, amount, type) => {
    const isDeduction = amount < 0;
    if (isDeduction) {
      const bar = Math.abs(amount);
      running += amount; // running decreases
      items.push({ name, base: running, bar, type, amount });
    } else {
      // Revenue or profit: bar from 0
      items.push({ name, base: 0, bar: amount, type, amount });
    }
  };

  push('Revenue', rev, 'revenue');
  push('Energy', -energy_total, 'cost');
  push('Crew', -crew_total, 'cost');
  push('Maintenance', -maint_total, 'cost');
  push('Landing', -land_total, 'cost');
  push('Capex', -capex, 'capex');
  // Net profit bar: from 0 to profit (already = running after all deductions)
  items.push({ name: 'Net', base: 0, bar: Math.abs(profit), type: profit >= 0 ? 'profit' : 'loss', amount: profit });

  return items;
}

/**
 * Binding constraint: identifies the primary reason the route is viable or not.
 * Returns a plain-language diagnosis for the InsightCard.
 */
export function computeBindingConstraint(result, vehicle) {
  const {
    range_feasible, breakeven_load_factor, annual_profit,
    energy_share, crew_share, maintenance_share, landing_share,
    payback_years, breakeven_fare_per_seat, load_factor, casm, rasm,
  } = result;

  if (!range_feasible) return {
    severity: 'critical',
    label: 'Range infeasible',
    detail: `Route distance exceeds ${vehicle.name}'s practical segment limit (${vehicle.max_range_segment_km} km with 20% energy reserve). The vehicle cannot complete this route safely.`,
    lever: `Shorten route to ≤${vehicle.max_range_segment_km} km, or switch to Joby S4 (200 km limit)`,
  };

  if (breakeven_load_factor > 1.0) return {
    severity: 'critical',
    label: 'Structurally loss-making',
    detail: `Even at 100% load factor with zero empty seats, revenue cannot cover costs. This route is not viable at the current fare.`,
    lever: `Raise fare to at least ${fmt_usd(breakeven_fare_per_seat)}/seat, or cut costs`,
  };

  if (breakeven_load_factor > 0.85) return {
    severity: 'high',
    label: 'Break-even load factor is unrealistic',
    detail: `This route needs ${fmt_pct(breakeven_load_factor)} load factor to break even. UAM routes realistically achieve 60–75%. Profitability is structurally difficult.`,
    lever: `Raise fare to ${fmt_usd(result.breakeven_fare_per_seat)}/seat, or reduce deadhead with better demand forecasting`,
  };

  if (energy_share > 0.35) return {
    severity: breakeven_load_factor > 0.70 ? 'high' : 'medium',
    label: 'Energy cost dominates opex',
    detail: `Energy is ${fmt_pct(energy_share)} of per-flight cost. Economics are highly sensitive to electricity tariff and vehicle efficiency. Reserve requirement adds 25% to raw energy needs.`,
    lever: `Negotiate grid tariff below $0.10/kWh, or use on-site solar with battery buffer`,
  };

  if (crew_share > 0.28 && vehicle.piloted) return {
    severity: breakeven_load_factor > 0.70 ? 'high' : 'medium',
    label: 'Pilot cost is the margin constraint',
    detail: `Crew cost is ${fmt_pct(crew_share)} of per-flight opex. Autonomous operations would cut this substantially (to ~$12/FH remote-ops cost vs $95/FH for a pilot).`,
    lever: `Autonomous successor (e.g. Wisk) would improve margin by ~${fmt_usd(result.crew_cost * result.annual_flights * 0.85)} annually`,
  };

  if (landing_share > 0.25) return {
    severity: 'medium',
    label: 'Landing fees erode margin on short routes',
    detail: `Landing fees are ${fmt_pct(landing_share)} of opex — disproportionately high on a ${result.distance_km} km route. The fixed cost per landing hurts short segments most.`,
    lever: `Longer routes amortize the fee better, or negotiate vertiport agreements below $20/landing`,
  };

  if (payback_years > 12) return {
    severity: 'medium',
    label: 'Capex payback horizon is long',
    detail: `Payback of ${fmt_num(payback_years, 1)} years approaches aircraft useful life. The investment case is thin even with positive annual profit.`,
    lever: `Increase fleet utilization or negotiate lower aircraft acquisition price at volume`,
  };

  return {
    severity: 'ok',
    label: 'Route is economically viable',
    detail: `Break-even at ${fmt_pct(breakeven_load_factor)} load factor — well below the 70% UAM industry target. Payback in ${fmt_num(payback_years, 1)} years.`,
    lever: `Focus on network density and vertiport throughput to sustain utilization above break-even`,
  };
}

export function fmt_usd(v, decimals = 0) {
  if (!isFinite(v)) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD',
    minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  }).format(v);
}

export function fmt_pct(v, decimals = 1) {
  if (!isFinite(v)) return '—';
  return (v * 100).toFixed(decimals) + '%';
}

export function fmt_num(v, decimals = 1) {
  if (!isFinite(v)) return '—';
  return v.toFixed(decimals);
}
