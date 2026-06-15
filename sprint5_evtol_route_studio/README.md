# Sprint 5 — eVTOL Route Viability Studio

Unit economics engine for urban air mobility routes.

**Stack:** React · Recharts · Vite (pure frontend, no backend)

---

## What it does

Most UAM tools answer: *"Can this eVTOL fly this route?"*  
This tool answers: *"Does this route make money, and under what conditions does it break?"*

The tool models the full unit economics of an eVTOL route — CASM, break-even utilization, annual P&L, and input sensitivity — using named real vehicles (Joby S4, Archer Midnight, Wisk Gen 6) with published specs, benchmarked against helicopter charter and regional aviation costs.

**Distinct from Sprint 2 (Drone Deployment Decision Engine):**  
Sprint 2 identifies the binding regulatory or physical constraint for a drone operation (go/no-go verdict). Sprint 5 is an economics model — output is a viability curve and sensitivity surface, not a constraint label. The question is financial, not regulatory.

---

## The model

**Inputs (user-adjustable):**
- Vehicle: Joby S4 · Archer Midnight · Wisk Gen 6 · Custom
- Route: segment distance, fare per seat, load factor
- Operations: electricity price, pilot cost/FH, landing fees, turnaround time, availability, infra capex

**Per-flight economics:**
```
Revenue / flight = fare × seats × load_factor
Energy cost      = kWh_per_seat_km × distance × seats × electricity_price
Crew cost        = pilot_$/FH × flight_hours  [0 if autonomous]
Maintenance      = $/FH × flight_hours
Total opex       = energy + crew + maintenance + landing_fee
```

**Annual economics (per aircraft):**
```
Flights/day     = floor(16h × 60 / cycle_time_min)
Annual flights  = flights/day × 365 × availability_factor
Annual revenue  = revenue/flight × annual_flights
Annual opex     = opex/flight × annual_flights
Annual capex    = (aircraft_cost / life_years) + (infra_capex / life_years)
Annual profit   = revenue − opex − capex
```

**Key outputs:**
1. **Annual profit / aircraft** — viability signal
2. **Break-even load factor** — at what utilization the route crosses into profit
3. **CASM** — cost per available seat-mile, benchmarked vs helicopter / Uber Black / regional jet
4. **Annual P&L waterfall** — revenue → energy → crew → maintenance → landing → capex → net
5. **Break-even curve** — annual profit as a function of load factor (0–100%)
6. **Sensitivity tornado** — which input has the highest leverage on annual profit (±20% perturbation)
7. **Payback period** — years to recover fleet + infra capex from net operating margin

**Viability classification:**
- ✓ **Viable**: break-even LF < 70%
- ⚠ **Marginal**: break-even LF 70–95%
- ✗ **Unviable**: break-even LF > 95%

---

## Vehicle specs

| Vehicle | Seats | Range | Battery | kWh/seat-km | Source |
|---|---|---|---|---|---|
| Joby S4 | 4 | 240 km | 254 kWh | 0.185 | Joby SEC S-1 2021 |
| Archer Midnight | 4 | 97 km | 140 kWh | 0.210 | Archer SEC 10-K 2023 |
| Wisk Gen 6 | 1 | 145 km | ~60 kWh | 0.480 | Wisk press release 2023 |

Energy intensity (kWh/seat-km) derived from battery capacity, range, seat count, and an 80–86% system efficiency assumption. Aircraft unit costs from NREL 2023 UAM Economic Analysis (at-scale projections).

---

## Competitive benchmarks

| Mode | CASM |
|---|---|
| Helicopter charter | $4.20/ASM |
| Uber Black (equiv.) | $1.80/ASM |
| Regional jet (50-seat) | $0.28/ASM |

Sources: [FAA-HELO] FAA general aviation helicopter survey 2022 · [DOT-2023] BTS airline CASM data

---

## How to run

```bash
cd sprint5_evtol_route_studio
npm install
npm run dev
```

Build for deployment:
```bash
npm run build
```

---

## Polaris context

Sprint 5 of the [Polaris Decision Modeling Studio](../README.md).  
Previous sprints: Scenario Explorer · Drone Decision Engine · Battery Risk Studio · Founder FMEA

*Engineering clarity for complex futures.*
