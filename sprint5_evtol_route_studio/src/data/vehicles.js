/**
 * eVTOL vehicle specifications — Sprint 5, Polaris Decision Modeling Studio
 *
 * Sources:
 * [JOBY-S1]     Joby Aviation — SEC S-1 filing, 2021; FAA Part 135 type cert docs, 2023
 * [ARCHER-10K]  Archer Aviation — SEC 10-K 2023; DOT/FAA certification basis
 * [WISK-PR]     Wisk Aero Gen 6 — press release Dec 2023; FAA Part 23 cert application
 * [NREL-2023]   NREL "Advanced Air Mobility Economic Analysis", 2023
 * [BOOZ-2023]   Booz Allen Hamilton "UAM Market Study" for NASA, 2023
 * [NASA-UAM]    NASA UAM Market Study, Oct 2018
 * [FAA-HELO]    FAA General Aviation Survey — helicopter operating costs, 2022
 * [DOT-2023]    BTS Airline CASM data, 2023
 */

export const VEHICLES = {
  joby_s4: {
    id: 'joby_s4',
    name: 'Joby S4',
    manufacturer: 'Joby Aviation',
    status: 'FAA Part 135 type cert in progress (2024–25)',
    seats_passenger: 4,
    piloted: true,
    remote_ops_cost_per_fh: 0,       // piloted — no remote ops cost
    range_km: 240,                    // [JOBY-S1] 150 miles
    cruise_speed_kmh: 320,            // [JOBY-S1] 200 mph
    battery_kwh: 254,                 // [JOBY-S1]
    kWh_per_seat_km: 0.185,          // derived: full-battery / (range × seats × 0.80 eff)
    charge_time_min: 10,              // [JOBY-S1] rapid charge target (full battery)
    min_ground_time_min: 8,           // boarding/deboarding minimum regardless of charge state
    aircraft_cost_usd: 3_200_000,    // [NREL-2023] at-scale projection
    useful_life_years: 12,
    maintenance_per_fh_usd: 130,     // flight-hour component [BOOZ-2023]
    maintenance_per_cycle_usd: 45,   // per-cycle component (battery, rotor wear) — estimated
    max_range_segment_km: 200,        // 80% of rated range (reserve buffer)
    notes: 'Tilt-rotor; quietest certified eVTOL. Primary UAM corridor: SF → SJ.',
    color: '#4A90D9',
  },

  archer_midnight: {
    id: 'archer_midnight',
    name: 'Archer Midnight',
    manufacturer: 'Archer Aviation',
    status: 'FAA Part 135 type cert in progress (2025)',
    seats_passenger: 4,
    piloted: true,
    remote_ops_cost_per_fh: 0,
    range_km: 97,                     // [ARCHER-10K] 60 miles
    cruise_speed_kmh: 241,            // [ARCHER-10K] 150 mph
    battery_kwh: 140,                 // [ARCHER-10K]
    kWh_per_seat_km: 0.210,
    charge_time_min: 10,
    min_ground_time_min: 8,
    aircraft_cost_usd: 2_800_000,    // [NREL-2023]
    useful_life_years: 12,
    maintenance_per_fh_usd: 115,
    maintenance_per_cycle_usd: 40,
    max_range_segment_km: 80,
    notes: 'Fixed-wing lift + cruise propulsors. Shorter range, lower cost. LA metro focus.',
    color: '#E8813A',
  },

  wisk_gen6: {
    id: 'wisk_gen6',
    name: 'Wisk Gen 6',
    manufacturer: 'Wisk Aero (Boeing)',
    status: 'FAA Part 23 cert application filed 2023',
    seats_passenger: 1,
    piloted: false,
    // Autonomous ≠ free. FAA requires remote pilot oversight.
    // Assume 1 operator monitors 8 aircraft @ $95/h loaded → $11.88/FH/aircraft [estimated]
    remote_ops_cost_per_fh: 12,
    range_km: 145,                    // [WISK-PR] 90 miles
    cruise_speed_kmh: 193,            // [WISK-PR]
    battery_kwh: 60,                  // [WISK-PR] estimated
    kWh_per_seat_km: 0.480,          // high per-seat: only 1 revenue seat
    charge_time_min: 15,
    min_ground_time_min: 5,          // no boarding assistance needed
    aircraft_cost_usd: 1_500_000,    // [NREL-2023]
    useful_life_years: 10,
    maintenance_per_fh_usd: 70,
    maintenance_per_cycle_usd: 25,
    max_range_segment_km: 120,
    notes: 'Autonomous (remote-supervised). Single passenger. Low vehicle cost, but yield limited by 1-seat capacity. Viable on high-frequency short urban hops.',
    color: '#2DBD7E',
  },

  custom: {
    id: 'custom',
    name: 'Custom Vehicle',
    manufacturer: '—',
    status: 'User-defined',
    seats_passenger: 4,
    piloted: true,
    remote_ops_cost_per_fh: 0,
    range_km: 150,
    cruise_speed_kmh: 250,
    battery_kwh: 200,
    kWh_per_seat_km: 0.200,
    charge_time_min: 12,
    min_ground_time_min: 8,
    aircraft_cost_usd: 3_000_000,
    useful_life_years: 12,
    maintenance_per_fh_usd: 130,
    maintenance_per_cycle_usd: 40,
    max_range_segment_km: 120,
    notes: 'All parameters user-defined.',
    color: '#9B59B6',
  },
};

/**
 * Aviation-comparable benchmarks for CASM
 * Uber Black excluded — ground $/mile ≠ aviation $/ASM (different seat-mile basis)
 */
export const BENCHMARKS = [
  { name: 'Helicopter charter', casm_usd: 4.20, color: '#666', note: '[FAA-HELO] $3–6 range' },
  { name: 'Turboprop (19-seat)', casm_usd: 0.72, color: '#555', note: '[DOT-2023] Cape Air / regional' },
  { name: 'Regional jet (50-seat)', casm_usd: 0.28, color: '#444', note: '[DOT-2023] BTS average' },
];

export const DEFAULT_ROUTE = {
  distance_km: 60,
  fare_per_seat_usd: 75,
  load_factor: 0.72,    // 72% — Joby/Archer investor presentations target
};

export const DEFAULT_OPERATIONS = {
  electricity_price_usd_kwh: 0.14,       // US commercial average 2023, EIA
  pilot_cost_per_fh_usd: 95,             // ATP-rated pilot, ~$95/FH loaded [BLS-2023]
  landing_fee_usd: 40,                    // per landing; vertiport estimate [NASA-UAM]
  infrastructure_capex_per_aircraft: 300_000,
  availability_factor: 0.85,
  turnaround_time_min: 15,
  energy_reserve_pct: 0.20,              // FAA-style minimum reserve: 20% of battery
  deadhead_factor: 0.15,                  // ~15% of flights reposition empty [BOOZ-2023]
};
