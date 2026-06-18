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
    energy_reserve_pct,        // fraction of battery held as reserve (default 0.20)
    deadhead_factor,           // fraction of flights that are empty repositioning (default 0.15)
    demand_utilization_pct = 1.0,  // fraction of slot capacity actually filled
    operating_hours_per_day = 16,  // daily ops window
  } = ops;

  // --- Flight physics ---
  const flight_time_h = distance_km / vehicle.cruise_speed_kmh;
  const flight_time_min = flight_time_h * 60;

  // Ground time: bounded below by THREE constraints — vehicle's physical
  // boarding minimum, the operator's procedural turnaround target, and the
  // charge time the energy budget actually needs. Whichever is largest wins.
  const mission_kwh_raw = vehicle.kWh_per_seat_km * distance_km * vehicle.seats_passenger;
  const energy_reserve_factor = 1 / (1 - energy_reserve_pct);
  const energy_kwh_with_reserve = mission_kwh_raw * energy_reserve_factor;
  const battery_fraction_used = mission_kwh_raw / vehicle.battery_kwh;
  // Proportional charge time (linear approximation at rapid-charge rate):
  const proportional_charge_min = battery_fraction_used * vehicle.charge_time_min;
  // All three are floors on ground time. Without including turnaround here,
  // moving the turnaround slider had no effect on cycle time — a regression
  // from the earlier Math.min fix. Now turnaround acts as a true operational
  // floor (slot booking, paperwork, crew handoff).
  const ground_time_min = Math.max(
    vehicle.min_ground_time_min,
    turnaround_time_min,
    proportional_charge_min,
  );
  const cycle_time_min = flight_time_min + ground_time_min;
  // Schedule-pressure flag: actual charging demand exceeds what the operator
  // planned for in their turnaround target.
  const charge_exceeds_turnaround = proportional_charge_min > turnaround_time_min;

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
  // Capacity = how many flights the cycle time allows in the daily ops window.
  // Realised = capacity × demand_utilization.
  //
  // SMOOTHNESS: keep flights/day continuous for ALL economics math, only
  // round for display. Previously, Math.floor(capacity) and Math.round(realised)
  // propagated into annual P&L and produced a visible staircase as inputs
  // moved continuously. A real fleet's *annual* output is fractional; the
  // user-facing daily integer is just a display convenience.
  const flights_per_day_capacity_continuous = (operating_hours_per_day * 60) / cycle_time_min;
  const flights_per_day_capacity = Math.floor(flights_per_day_capacity_continuous);   // display only
  const flights_per_day_continuous = flights_per_day_capacity_continuous * demand_utilization_pct;
  const flights_per_day = Math.max(1, Math.round(flights_per_day_continuous));        // display only
  // Annual P&L: continuous through every step — no rounding.
  const annual_flights_total = flights_per_day_continuous * 365 * availability_factor;
  // Revenue-generating flights: total minus deadhead repositioning flights.
  // Continuous (no round) so annual_revenue stays smooth under input sweeps.
  const annual_flights_revenue = annual_flights_total * (1 - deadhead_factor);

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

  // --- CASM / RASM (industry standard: both on TOTAL ASM) ---
  // Computing RASM on the revenue-only denominator inflates it and breaks the
  // RASM-vs-CASM comparison whenever deadhead > 0 (you can show RASM > CASM
  // even when revenue doesn't cover opex). Industry convention is that both
  // metrics use the same denominator — total available seat-miles, including
  // empty repositioning flights — so comparing them is meaningful.
  const distance_miles = distance_km * KM_TO_MILES;
  const available_seat_miles_total = vehicle.seats_passenger * annual_flights_total * distance_miles;
  const casm = available_seat_miles_total > 0 ? annual_opex / available_seat_miles_total : 0;
  const rasm = available_seat_miles_total > 0 ? annual_revenue / available_seat_miles_total : 0;
  // Revenue yield per revenue-ASM (useful as a separate diagnostic — what
  // paying seats actually pay per mile). Kept distinct from RASM to avoid
  // mixing the two concepts.
  const available_seat_miles_revenue = vehicle.seats_passenger * annual_flights_revenue * distance_miles;
  const yield_per_rasm = available_seat_miles_revenue > 0 ? annual_revenue / available_seat_miles_revenue : 0;

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
  // Two independent constraints can bind:
  //   (a) Segment cap: the operator/vehicle spec's max single-leg distance.
  //   (b) Energy: usable battery after reserve must cover the mission.
  // Use the stricter of the two — and tell the UI which one binds, so the
  // diagnosis can name the real constraint (operational vs. physics).
  const usable_battery_kwh    = vehicle.battery_kwh * (1 - energy_reserve_pct);
  const kwh_per_km_at_load    = vehicle.kWh_per_seat_km * vehicle.seats_passenger;
  const max_distance_energy_km = kwh_per_km_at_load > 0
    ? usable_battery_kwh / kwh_per_km_at_load
    : Infinity;
  const max_distance_segment_km = vehicle.max_range_segment_km;
  const max_distance_effective_km = Math.min(max_distance_energy_km, max_distance_segment_km);

  let range_constraint = 'ok';
  if (distance_km > max_distance_energy_km) range_constraint = 'energy';
  else if (distance_km > max_distance_segment_km) range_constraint = 'segment';

  const range_feasible = distance_km <= max_distance_effective_km;

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
    flights_per_day_capacity,        // theoretical max if every slot were filled
    demand_utilization_pct,          // echo so UI can label the gap
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

    casm, rasm, yield_per_rasm,
    breakeven_load_factor,
    breakeven_fare_per_seat,
    payback_years,

    energy_share, crew_share, maintenance_share, landing_share,
    range_feasible,
    range_constraint,                       // 'ok' | 'energy' | 'segment'
    max_distance_energy_km,                 // physics limit
    max_distance_segment_km,                // operational limit
    max_distance_effective_km,              // min of the two
    charge_exceeds_turnaround,              // schedule infeasibility flag
    ground_time_min,                        // exposed so UI can show "X min ground" if needed
    deadhead_factor,                        // echo back so UI components don't need the ops object
  };
}

/**
 * Break-even curve: annual profit vs load factor (0–100%).
 * 1% resolution so chart hover snaps at 1pp, not 5pp.
 */
export function computeBreakevenCurve(vehicle, route, ops) {
  const points = [];
  for (let i = 0; i <= 100; i += 1) {
    const lf = i / 100;
    const r = computeEconomics(vehicle, { ...route, load_factor: lf }, ops);
    points.push({
      load_factor_pct: i,
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

  // Per-input physical bounds. Without clamping, a 0.85 load factor under
  // +20% becomes 1.02 — over 100% — and computeEconomics happily computes
  // revenue as if you sold more seats than the aircraft has. That makes
  // load_factor's leverage bar nonsense whenever the user dials LF above ~0.83.
  const bounds = {
    load_factor:             [0, 1],
    availability_factor:     [0, 1],
    demand_utilization_pct:  [0.01, 1],
    deadhead_factor:         [0, 0.9],
    energy_reserve_pct:      [0.01, 0.6],
  };
  const clamp = (key, v) => {
    const b = bounds[key];
    return b ? Math.max(b[0], Math.min(b[1], v)) : v;
  };

  // Pilot cost is irrelevant for autonomous vehicles — drop it.
  // Fare and LF are mathematically equivalent revenue levers (both scale
  // revenue linearly by the same factor); flagged in `note` so the UI can
  // explain why the bars are identical.
  const allInputs = [
    { key: 'fare_per_seat_usd',         label: 'Fare per seat',          type: 'route', direction: 'up_good',   note: 'lf_equiv' },
    { key: 'load_factor',               label: 'Load factor',            type: 'route', direction: 'up_good',   note: 'lf_equiv' },
    { key: 'deadhead_factor',           label: 'Deadhead rate',          type: 'ops',   direction: 'down_good' },
    { key: 'demand_utilization_pct',    label: 'Demand utilization',     type: 'ops',   direction: 'up_good',   note: 'margin_dep' },
    { key: 'availability_factor',       label: 'Aircraft availability',  type: 'ops',   direction: 'up_good',   note: 'margin_dep' },
    { key: 'electricity_price_usd_kwh', label: 'Electricity price',      type: 'ops',   direction: 'down_good' },
    { key: 'energy_reserve_pct',        label: 'Energy reserve',         type: 'ops',   direction: 'down_good' },
    { key: 'pilot_cost_per_fh_usd',     label: 'Pilot cost/FH',          type: 'ops',   direction: 'down_good', requiresPiloted: true },
    { key: 'landing_fee_usd',           label: 'Landing fee',            type: 'ops',   direction: 'down_good' },
    { key: 'turnaround_time_min',       label: 'Turnaround time',        type: 'ops',   direction: 'down_good' },
    { key: 'infrastructure_capex_per_aircraft', label: 'Infra capex/aircraft', type: 'ops', direction: 'down_good' },
  ];
  const inputs = allInputs.filter(i => !i.requiresPiloted || vehicle.piloted);

  return inputs.map(({ key, label, type, direction, note }) => {
    const src = type === 'route' ? route : ops;
    const baseVal = src[key];
    const upVal   = clamp(key, baseVal * (1 + delta));
    const downVal = clamp(key, baseVal * (1 - delta));

    const upResult = type === 'route'
      ? computeEconomics(vehicle, { ...route, [key]: upVal }, ops)
      : computeEconomics(vehicle, route, { ...ops, [key]: upVal });

    const downResult = type === 'route'
      ? computeEconomics(vehicle, { ...route, [key]: downVal }, ops)
      : computeEconomics(vehicle, route, { ...ops, [key]: downVal });

    const impact_up = upResult.annual_profit - base.annual_profit;
    const impact_down = downResult.annual_profit - base.annual_profit;

    // Asymmetric leverage flag: when the +20% direction is clamped, the
    // displayed (up) bar understates true leverage. The tooltip uses this
    // to warn the user that the down-side is bigger.
    const asymmetric = Math.abs(Math.abs(impact_up) - Math.abs(impact_down)) /
                       Math.max(Math.abs(impact_up), Math.abs(impact_down), 1) > 0.10;

    return {
      key, label, direction, note,
      base_val: baseVal,
      up_val:   upVal,
      down_val: downVal,
      clamped:  upVal !== baseVal * (1 + delta) || downVal !== baseVal * (1 - delta),
      asymmetric,
      impact_up,
      impact_down,
      abs_impact: Math.max(Math.abs(impact_up), Math.abs(impact_down)),
    };
    // Sort by |impact_up| — matches what the bar displays, so a bigger bar
    // is always higher in the list. The previous sort by max(|up|,|down|)
    // caused clamped inputs (e.g. availability at LF→1.0) to rank above
    // smaller-bar inputs, which looked like a UI bug.
  }).sort((a, b) => Math.abs(b.impact_up) - Math.abs(a.impact_up));
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

  if (!range_feasible) {
    const limit_km = Math.round(result.max_distance_effective_km);
    if (result.range_constraint === 'energy') {
      return {
        severity: 'critical',
        label: 'Range infeasible — energy budget',
        detail: `At a ${(result.energy_kwh / result.energy_kwh_raw - 1) * 0 + 0}km route this vehicle's usable battery (after reserve) only supports ~${limit_km} km with a full payload. The mission would draw below the safety reserve.`,
        lever: `Shorten route to ≤${limit_km} km, fly with lighter payload, or pick a higher-capacity vehicle`,
      };
    }
    return {
      severity: 'critical',
      label: 'Range infeasible — operator segment cap',
      detail: `Route exceeds ${vehicle.name}'s declared operational segment limit (${vehicle.max_range_segment_km} km). Energy alone could fly ~${Math.round(result.max_distance_energy_km)} km, but operations don't approve longer single legs for this airframe.`,
      lever: `Shorten route to ≤${vehicle.max_range_segment_km} km, or revisit the segment-cap assumption`,
    };
  }

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

/**
 * Monte Carlo: P10 / P50 / P90 annual profit under input uncertainty.
 *
 * Each input is drawn from a triangular distribution between (low, base, high).
 * Triangular is the right shape for "I have a best guess plus a range" — it's
 * standard in engineering risk analysis and doesn't require the user to think
 * about variance. n_draws of 2000 runs in <100 ms in the browser.
 *
 * The ranges below reflect plausible operator uncertainty, NOT model error:
 *   - fare ± 25%        (yield management uncertainty)
 *   - load factor ± 15 pp absolute, clamped to [0.20, 0.95]
 *   - electricity ± 30% (PPA negotiation, time-of-use)
 *   - deadhead ± 10 pp absolute, clamped to [0, 0.40]
 *   - demand utilization ± 20 pp absolute, clamped to [0.10, 1.0]
 *   - availability ± 10 pp absolute, clamped to [0.50, 0.99]
 *   - landing fee ± 50% (vertiport pricing is unsettled)
 */
function _triangular(low, mode, high, rng) {
  const u = rng();
  const f = (mode - low) / (high - low);
  if (u < f) return low + Math.sqrt(u * (high - low) * (mode - low));
  return high - Math.sqrt((1 - u) * (high - low) * (high - mode));
}

function _seededRng(seed = 1234567) {
  // mulberry32 — small, fast, deterministic. Same draw each render for
  // chart stability (re-runs only change when inputs change).
  let s = seed >>> 0;
  return function () {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function _clamp(x, lo, hi) { return Math.max(lo, Math.min(hi, x)); }

export function computeMonteCarlo(vehicle, route, ops, n_draws = 2000) {
  const rng = _seededRng();
  const profits = new Float64Array(n_draws);

  for (let i = 0; i < n_draws; i++) {
    const r = {
      ...route,
      fare_per_seat_usd: _triangular(
        route.fare_per_seat_usd * 0.75,
        route.fare_per_seat_usd,
        route.fare_per_seat_usd * 1.25,
        rng,
      ),
      load_factor: _clamp(
        _triangular(route.load_factor - 0.15, route.load_factor, route.load_factor + 0.15, rng),
        0.20, 0.95,
      ),
    };
    const o = {
      ...ops,
      electricity_price_usd_kwh: _triangular(
        ops.electricity_price_usd_kwh * 0.70,
        ops.electricity_price_usd_kwh,
        ops.electricity_price_usd_kwh * 1.30,
        rng,
      ),
      deadhead_factor: _clamp(
        _triangular(ops.deadhead_factor - 0.10, ops.deadhead_factor, ops.deadhead_factor + 0.10, rng),
        0, 0.40,
      ),
      demand_utilization_pct: _clamp(
        _triangular(
          (ops.demand_utilization_pct ?? 0.60) - 0.20,
          ops.demand_utilization_pct ?? 0.60,
          (ops.demand_utilization_pct ?? 0.60) + 0.20,
          rng,
        ),
        0.10, 1.0,
      ),
      availability_factor: _clamp(
        _triangular(ops.availability_factor - 0.10, ops.availability_factor, ops.availability_factor + 0.10, rng),
        0.50, 0.99,
      ),
      landing_fee_usd: _triangular(
        ops.landing_fee_usd * 0.50,
        ops.landing_fee_usd,
        ops.landing_fee_usd * 1.50,
        rng,
      ),
    };
    profits[i] = computeEconomics(vehicle, r, o).annual_profit;
  }

  // Sort for percentiles
  const sorted = Array.from(profits).sort((a, b) => a - b);
  const pct = (p) => sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))];

  // Histogram (40 bins)
  const lo = sorted[0];
  const hi = sorted[sorted.length - 1];
  const nbins = 40;
  const width = (hi - lo) / nbins || 1;
  const bins = Array.from({ length: nbins }, (_, i) => ({
    x0: lo + i * width,
    x1: lo + (i + 1) * width,
    mid: lo + (i + 0.5) * width,
    count: 0,
  }));
  for (const v of profits) {
    const idx = Math.min(nbins - 1, Math.floor((v - lo) / width));
    bins[idx].count += 1;
  }

  const prob_profitable = profits.reduce((acc, v) => acc + (v > 0 ? 1 : 0), 0) / n_draws;

  return {
    n_draws,
    p10: pct(0.10),
    p50: pct(0.50),
    p90: pct(0.90),
    mean: profits.reduce((a, b) => a + b, 0) / n_draws,
    prob_profitable,
    bins,
    min: lo,
    max: hi,
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
