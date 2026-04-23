# MODEL_SPRINT2.md — Polaris Drone Deployment Decision Engine v1

## 1. What this is

Polaris Sprint 2 is a **deployment decision tool** for organizations evaluating whether to integrate
commercial drones into their operations.

It translates user-defined scenario parameters into structured, benchmark-referenced outputs —
answering not just "what would it cost?" but **"should you deploy drones here, now, and how?"**

Built for:
- **Utilities and energy companies** — evaluating drone inspection of power lines, wind turbines, pipelines
- **Logistics and e-commerce operators** — stress-testing last-mile drone delivery economics
- **Agricultural operations** — assessing whether drone spraying/mapping pays off at their scale
- **Consulting teams and investors** — structuring go/no-go conversations with traceable references

The tool produces a deployment verdict with an explicit **binding constraint label** — telling the user
not just that a scenario fails, but *exactly what* needs to change to make it viable.

---

## 2. What this is NOT

| It is NOT | Why this matters |
|---|---|
| A platform comparison tool | It doesn't rank specific drone models; it uses platform tiers as economic proxies |
| A regulatory compliance checker | It flags regulatory constraints; it does not replace legal review of waiver applications |
| A logistics optimization model | It does not route drones or optimize delivery networks |
| A certified engineering analysis | Cost coefficients are industry reference values, not operator-specific audited data |
| A financial forecasting tool | Outputs are decision-support proxies, not auditable P&L projections |
| A predictive model | Outputs show what assumptions imply under current conditions, not what will happen |

The design principle: **every cost coefficient has a derivation, every regulatory reference has a source,
every constraint label has a traceable logic. If you disagree with a number, we can trace it to its
source and discuss alternatives.**

---

## 3. Primary sources

Every parameter in this model is traced to one of these published documents or verifiable data sources:

| Reference key | Full citation |
|---|---|
| **[FAA-107]** | FAA, *14 CFR Part 107 — Small Unmanned Aircraft Systems*, effective August 29, 2016; amended December 28, 2020 |
| **[FAA-108]** | FAA, *Notice of Proposed Rulemaking: Normalizing UAS Beyond Visual Line of Sight Operations (Part 108)*, Federal Register Vol. 90, August 7, 2025 |
| **[FAA-2024]** | FAA, *CY 2024 Small Unmanned Aircraft Systems Survey Report*, 2025 |
| **[FAA-CONOPS]** | FAA, *Drone Integration: Concept of Operations*, Version 1.0, May 2025 |
| **[DOT-OIG]** | DOT Office of Inspector General, *FAA Has Made Progress in Advancing BVLOS Drone Operations*, June 30, 2025 |
| **[MU-EXT]** | University of Missouri Extension, *Economics of Drone Ownership for Agricultural Spray Applications* (Publication G1274), 2024 |
| **[PwC-2016]** | PwC, *Clarity from Above: PwC Global Report on the Commercial Applications of Drone Technology*, 2016 |
| **[AUVSI-MAP]** | AUVSI, *Unmanned Systems Integrated Roadmap 2020–2045*, 2020 |
| **[BARCLAYS-2026]** | Barclays Equity Research, *Drone Delivery Could Unlock $16B in Profits*, April 2026 |
| **[MANNA-2025]** | Manna Drone Delivery, operational and investor disclosures, 2024–2025 |

---

## 4. Regulatory framework constants

### 4.1 Visual Line of Sight (VLOS) — Part 107 baseline

Under 14 CFR Part 107, the remote pilot in command must maintain **unaided visual line of sight**
with the UAS at all times. [FAA-107] §107.31.

Practical VLOS operational radius: **≤ 1.5 km** one-way from the operator under standard daytime
conditions in open terrain. This limit is not codified as a fixed distance in the regulation, but
is the operational standard accepted by the FAA Safety Team and used consistently in waiver applications.
Actual limit varies with aircraft size, visibility, and crew experience.

Operations at >1.5 km require either:
- A visual observer chain (mitigates range, not a BVLOS authorization), or
- A **BVLOS waiver under §107.31**, or
- A **Part 108 operating permit** (when the final rule takes effect)

### 4.2 BVLOS regulatory timeline

| Milestone | Date | Source |
|---|---|---|
| FAA Part 108 NPRM published | August 7, 2025 | [FAA-108] |
| Comment period closed | October 6, 2025 | [FAA-108] |
| Final rule expected | Spring 2026 | [FAA-108]; Pillsbury Law analysis |
| Implementation (earliest) | Late 2026 – Early 2027 | [FAA-108]; [DOT-OIG] |
| Current BVLOS waivers issued (total) | ~284 under §107.31 | [FAA-2024] |

**Implication for the model:** BVLOS is currently a high-friction, per-operation waiver process.
For scenarios requiring BVLOS, the regulatory status input determines whether the deployment is
currently viable (waiver held), pending, or blocked — with a note on the Part 108 unlock timeline.

### 4.3 Urban airspace constraint

Operations within FAA Class B, C, D, or surface E airspace require **LAANC authorization** or
manual FAA DroneZone authorization prior to flight — even for VLOS Part 107 operations.
[FAA-107] §107.41. This applies to most urban and suburban delivery scenarios.

---

## 5. Platform tiers

Three platform tiers abstract across the commercial UAS market. Each represents a class of currently
available commercial hardware as of 2024–2025. The model uses midpoint acquisition costs.

| Tier | Representative platforms | Acquisition cost (midpoint) | Max payload | Endurance | Max VLOS range (one-way) | Max BVLOS range (one-way) |
|---|---|---:|---:|---:|---:|---:|
| **Light** | DJI Mavic 3 Enterprise, Autel EVO II Enterprise | $6,500 | 0.9 kg | 42 min | 5 km | 10 km |
| **Professional** | DJI Matrice 350 RTK, Freefly ALTA X | $20,000 | 2.7 kg | 55 min | 8 km | 20 km |
| **Heavy** | DJI Matrice 4E, Wingtra ONE GEN II | $50,000 | 5.0 kg | 57 min | 12 km | 40 km |

**Notes:**
- Acquisition cost includes base platform only; payload sensors (thermal, multispectral, LiDAR) are
  additional costs not modeled here. Sensor costs typically range $2,000–$30,000 depending on type.
- BVLOS range assumes fixed-wing or extended-endurance configuration for the Heavy tier; rotary-wing
  platforms at Heavy tier have shorter effective BVLOS range (~25 km).
- Chinese-origin platforms (DJI, Autel) are subject to procurement restrictions for federal contracts
  and some regulated utilities under NDAA Section 848. This constraint is flagged in the model but
  not computed as a cost.

**Cruise speeds (used in flight time computation):**

| Tier | Cruise speed |
|---|---:|
| Light | 45 km/hr |
| Professional | 50 km/hr |
| Heavy | 55 km/hr (rotary) / 80 km/hr (fixed-wing) |

---

## 6. Economic constants

### 6.1 Direct operating cost components

**Depreciation:**
- Depreciation period: **3 years** (commercial UAS industry standard for active field operations) [MU-EXT]
- Formula: `platform_cost / (3 × annual_missions)`
- Rationale: commercial operators depreciate UAS over 3 years due to rapid technology evolution
  and physical wear from active deployment

**Battery replacement:**

| Tier | Battery set cost | Lifecycle (cycles) | Cost per mission |
|---|---:|---:|---:|
| Light | $300 | 250 | $1.20 |
| Professional | $450 | 250 | $1.80 |
| Heavy | $600 | 250 | $2.40 |

Lifecycle basis: LiPo battery degradation to 80% capacity threshold at 200–300 cycles under
normal operating conditions (15–35°C, standard discharge depth). Use 250 cycles as central estimate.
[Manufacturer specifications; industry operational guides]

**Remote pilot cost:**
- US certified commercial remote pilot (Part 107): **$65/hr** reference rate
- Basis: commercial drone service market rate range $55–$80/hr [commercial operator surveys, 2024]
- Setup time per mission: **0.5 hr** (pre-flight check, equipment setup, post-mission documentation)
- Total pilot cost per mission: `$65 × (flight_time_hr + 0.5)`

**Maintenance:**
- Annual maintenance rate: **15% of platform acquisition cost** [MU-EXT; PwC-2016 methodology]
- Per-mission: `(platform_cost × 0.15) / annual_missions`
- Covers: scheduled maintenance, propeller replacement, frame repairs, firmware updates

**Insurance:**

| Tier | Annual premium |
|---|---:|
| Light | $800 |
| Professional | $2,000 |
| Heavy | $4,000 |

Source: Commercial UAS insurance market rates, 2024. Figures represent third-party liability +
hull coverage for active commercial operations in the US.

### 6.2 Human alternative benchmarks

These are the reference costs for the human method that drones replace. All rates are US market
references.

**Inspection — helicopter:**
- Fully loaded rate: **$2,500/hr** (fuel, maintenance, two crew, mobilization amortized)
- Inspection patrol speed: **60 km/hr** (slow patrol altitude for infrastructure inspection)
- Source: helicopter charter industry rates; [PwC-2016]

**Inspection — rope access:**
- Cost per point asset (wind turbine, industrial structure): **$4,000/asset**
- Basis: typical 2-technician team, $100/hr/technician, 8–12 hr for turbine inspection including
  access setup and teardown; shutdown downtime costs not included
- Range: $3,000–$5,000/turbine [commercial inspection industry data, 2024]
- [PwC-2016] confirms 60–75% cost reduction potential for drone inspection vs. rope access

**Inspection — ground crew (bucket truck):**
- Fully loaded rate: **$150/hr** (2-person crew + vehicle + fuel)
- Ground coverage speed for power line inspection: **2.5 km/hr**
- Source: utility field operations benchmarks; [PwC-2016]

**Delivery — last mile:**

| Geography | Human alternative cost per stop | Basis |
|---|---:|---|
| Urban (dense) | $6 | Van/courier dense route; 30–50 stops/day amortized |
| Suburban | $12 | Van with longer inter-stop distances; 15–25 stops/day |
| Rural | $22 | Individual vehicle trip; <8 stops/day [BARCLAYS-2026] |

**Agriculture — aerial (manned crop duster):**
- Reference rate: **$15/acre**
- Basis: US manned aerial application industry rate for fungicide/pesticide; range $12.50–$20/acre
  depending on crop and application type [MU-EXT]

**Agriculture — ground sprayer:**
- Reference rate: **$6/acre**
- Basis: self-propelled ground sprayer operating cost including fuel, labor, equipment [MU-EXT]

### 6.3 Agriculture drone coverage rates

| Tier | Coverage rate |
|---|---:|
| Light | 8 acres/hr |
| Professional | 13 acres/hr |
| Heavy | 20 acres/hr |

Basis: DJI Agras T10 (10 acres/hr), DJI Agras T40 (21.5 acres/hr), mid-tier interpolated.
Rates assume full tank operations on flat to gently sloping terrain.

---

## 7. Inputs

All inputs are scenario parameters set by the user. They represent assumptions about a specific
deployment context — not measurements of an existing operation.

### 7.1 Use case

| Value | Description | Human alternative options |
|---|---|---|
| `inspection` | Drone inspects infrastructure or point assets | `helicopter`, `rope_access`, `ground_crew` |
| `delivery` | Drone completes last-mile package delivery | Determined by geography: `urban`, `suburban`, `rural` |
| `agriculture` | Drone sprays or surveys agricultural land | `aerial` (manned), `ground` (sprayer) |

### 7.2 Platform tier

`light` / `professional` / `heavy`

Determines physical constraints (payload, range, endurance) and fixed cost structure.
See Section 5.

### 7.3 Mission range (km, one-way)

Continuous input: 0.5–50 km.

This is the distance from the operator to the furthest point of the mission area.
The model computes round-trip flight time as `(mission_range × 2) / cruise_speed`.

For point-asset inspection (turbine, tower), use the on-site hover time instead of a range:
the model converts this to equivalent flight time.

**Derived parameter: BVLOS required**
`bvlos_required = (mission_range > 1.5 km)`

### 7.4 Payload (kg)

Continuous input: 0.1–10 kg.

Payload includes sensor packages (inspection) or cargo (delivery). The model checks this against
the platform tier's maximum payload. For agriculture, payload refers to spray tank weight and is
implicitly accounted for in the coverage rate coefficients.

### 7.5 BVLOS authorization status

| Value | Meaning |
|---|---|
| `authorized` | Operator holds a current Part 107 §107.31 waiver or will operate under Part 108 permit |
| `waiver_pending` | Application submitted; operations blocked pending FAA review (target: 90-day review) |
| `not_authorized` | No waiver, no permit; BVLOS operations are not currently permissible |

### 7.6 Annual mission volume

Continuous input: 10–5,000 missions per year.

Determines depreciation allocation per mission and break-even dynamics. Low volume = high
fixed-cost burden per mission. High volume = strong scale economics.

**Sensitivity note:** this is the second most influential variable for inspection and agriculture
use cases (after human alternative rate). See Section 10.

### 7.7 Geography type

`urban` / `suburban` / `rural` / `remote`

Used to: (1) set the delivery human alternative rate, (2) flag urban airspace authorization
requirements, (3) apply a labor cost context modifier.

### 7.8 Labor cost multiplier

| Value | Multiplier | Context |
|---|---:|---|
| `low` | 0.70× | Developing markets, low-wage labor environments |
| `standard` | 1.00× | US market reference (default) |
| `high` | 1.50× | High-cost metro areas, offshore/remote locations, union labor |

Applied to all human alternative rates. Does not affect drone operating costs.

---

## 8. Computation methodology

### 8.1 Platform constraint checks (pre-computation)

Before any cost calculation, the model performs hard constraint checks in priority order.
If any constraint is triggered, that constraint becomes the **binding constraint** and the
go/no-go verdict is issued immediately.

**Check 1 — Payload:**
```
IF payload > platform_max_payload[tier]:
    binding_constraint = "Payload exceeds platform capacity"
    verdict = NO-GO
```

**Check 2 — Range / endurance:**
```
platform_max_range = {
    light:        VLOS: 5 km / BVLOS: 10 km,
    professional: VLOS: 8 km / BVLOS: 20 km,
    heavy:        VLOS: 12 km / BVLOS: 40 km
}

IF bvlos_required:
    effective_max = platform_max_range[tier]["bvlos"]
ELSE:
    effective_max = platform_max_range[tier]["vlos"]

IF mission_range > effective_max:
    binding_constraint = "Mission range exceeds platform endurance"
    verdict = NO-GO
```

**Check 3 — Regulatory:**
```
IF bvlos_required AND bvlos_status == "not_authorized":
    binding_constraint = "BVLOS required but not authorized"
    verdict = NO-GO
    regulatory_note = "Part 108 framework expected 2026-2027 [FAA-108]"

IF bvlos_required AND bvlos_status == "waiver_pending":
    flag = "BVLOS waiver pending — deployment blocked until FAA approval"
    verdict = CONDITIONAL

IF geography == "urban" AND use_case == "delivery":
    flag += "Urban airspace: LAANC authorization required [FAA-107 §107.41]"
```

### 8.2 Flight time and mission duration

```
flight_time_hr = (mission_range × 2) / cruise_speed[tier]
setup_time_hr  = 0.5   # pre-flight + post-flight, all use cases
mission_duration_hr = flight_time_hr + setup_time_hr
```

For point-asset inspection (rope access benchmark use case), where the drone circles a turbine
or structure rather than traveling a linear distance:
```
flight_time_hr = 0.5   # 30 min standard thorough inspection flight per asset
mission_duration_hr = 1.0   # 0.5 hr flight + 0.5 hr setup
```

### 8.3 Drone direct operating cost (DOC) per mission

```
# Fixed cost components (scale with annual volume)
depreciation     = platform_cost[tier] / (3 × annual_missions)
maintenance      = (platform_cost[tier] × 0.15) / annual_missions
insurance        = insurance_annual[tier] / annual_missions

# Variable cost components (per mission)
battery          = battery_set_cost[tier] / 250
pilot            = pilot_rate × mission_duration_hr   # $65/hr × duration

# Total
drone_DOC = depreciation + maintenance + insurance + battery + pilot
```

**Variable costs** (battery + pilot) represent the minimum DOC at any volume.
**Fixed costs** (depreciation + maintenance + insurance) decrease as volume increases.

### 8.4 Human alternative cost per mission

**Inspection — helicopter:**
```
coverage_km = mission_range × 2   # round-trip linear coverage
heli_time   = coverage_km / 60 + 0.5   # patrol speed + mobilization
human_cost  = 2500 × heli_time × labor_multiplier
```

**Inspection — rope access:**
```
human_cost = 4000 × labor_multiplier   # per point asset
```

**Inspection — ground crew:**
```
coverage_km = mission_range × 2
ground_time = coverage_km / 2.5 + 0.5   # slow patrol + setup
human_cost  = 150 × ground_time × labor_multiplier
```

**Delivery:**
```
delivery_reference = {urban: 6, suburban: 12, rural: 22}   # $/stop
human_cost = delivery_reference[geography] × labor_multiplier
```

**Agriculture:**
```
acres_per_mission = coverage_rate[tier] × flight_time_hr
ag_reference      = {aerial: 15, ground: 6}   # $/acre
human_cost = ag_reference[human_method] × acres_per_mission × labor_multiplier
```

### 8.5 Economic metrics

```
cost_savings_per_mission = human_cost - drone_DOC
cost_savings_pct         = cost_savings_per_mission / human_cost × 100
annual_savings           = cost_savings_per_mission × annual_missions

# Break-even: how many missions to recover platform acquisition cost
break_even_volume        = platform_cost[tier] / max(cost_savings_per_mission, 0.01)
platform_payback_months  = (break_even_volume / annual_missions) × 12
```

### 8.6 Economic constraint checks

```
IF cost_savings_per_mission < 0:
    binding_constraint = "Drone more expensive than human alternative"
    verdict = NO-GO

IF cost_savings_per_mission > 0 AND annual_missions < (break_even_volume × 0.5):
    binding_constraint = "Insufficient utilization — high fixed-cost burden"
    verdict = CONDITIONAL
    recommendation = "Consider Drone-as-a-Service (DaaS) to avoid platform acquisition"
```

### 8.7 Final go/no-go verdict

If all checks pass (no binding constraint triggered):

```
verdict = GO
binding_constraint = "None"
```

**Binding constraint priority order:**
1. Payload (hardware incompatibility — cannot be waived)
2. Range / endurance (physics — cannot be waived)
3. Regulatory / BVLOS (legal — resolves via waiver or Part 108, ~2027)
4. Economic (drone costs exceed human alternative — rare, mainly vs. low-cost ground labor)
5. Scale / utilization (insufficient volume — resolves via volume growth or DaaS)
6. Urban airspace (conditional, not hard stop — resolves via LAANC authorization)

The model reports the **single highest-priority binding constraint** and a recommended path to resolution.

---

## 9. Go/No-Go zones

Go/No-Go zones are the model's primary output for decision conversations. Each zone has a label,
its trigger condition, and the explicit path to change the verdict.

| Zone | Label | Trigger condition | What changes the outcome |
|---|---|---|---|
| **Regulatory wall** | `"Not viable: BVLOS unauthorized"` | `mission_range > 1.5 km` AND `bvlos_status = not_authorized` | Obtain Part 107 §107.31 waiver (90-day process) or await Part 108 permit (expected 2026–27) |
| **Technology ceiling** | `"Not viable: range exceeds platform endurance"` | `mission_range > platform_max_range[tier][mode]` | Upgrade platform tier, or deploy intermediate relay / recharge station |
| **Payload limit** | `"Not viable: payload exceeds platform capacity"` | `payload > platform_max_payload[tier]` | Upgrade platform tier or reduce sensor payload |
| **Labor floor** | `"Not viable: drone cost exceeds human alternative"` | `drone_DOC > human_cost` | Switch human alternative benchmark (e.g., vs. helicopter instead of ground crew), or wait for platform cost reduction |
| **Scale threshold** | `"Marginal: viable above X missions/year"` | `annual_missions < break_even_volume × 0.5` | Increase utilization (contract more work), or switch to DaaS model |
| **Urban airspace** | `"Conditional: LAANC authorization required"` | `geography = urban` AND `use_case = delivery` | Obtain LAANC authorization through FAA DroneZone (automated, typically minutes) |
| **Go** | `"Viable under current parameters"` | All constraints pass | — |

**The key insight:** the tool does not return a generic "viable / not viable." It returns the
*specific* blocking factor and a traceable resolution path. This is what makes it useful as a
conversation tool — not a dashboard, but a structured argument.

---

## 10. Outputs and their units

| Output | Unit | What it measures |
|---|---|---|
| `drone_doc_per_mission` | USD | Total drone direct operating cost per mission |
| `human_cost_per_mission` | USD | Human alternative cost per equivalent mission |
| `cost_savings_per_mission` | USD | Human cost minus drone DOC |
| `cost_savings_pct` | % | Savings as percentage of human cost |
| `annual_savings` | USD/yr | Savings at the input annual mission volume |
| `break_even_volume` | missions/yr | Annual volume needed to recover platform cost |
| `platform_payback_months` | months | Time to break even at given annual volume |
| `verdict` | GO / CONDITIONAL / NO-GO | Deployment viability under current parameters |
| `binding_constraint` | text label | The single highest-priority blocking factor |
| `deployment_recommendation` | text | Narrative: what the scenario implies, what to change |

---

## 11. Key reference benchmarks

The dashboard compares scenario outputs against published reference points.

| Metric | Reference | Source | Type |
|---|---|---|---|
| Inspection cost reduction vs. helicopter | 70–80% | [PwC-2016]; industry data | Industry reference |
| Inspection cost reduction vs. rope access | 60–75% | [PwC-2016]; commercial data | Industry reference |
| Delivery viability threshold | < $10/delivery | [BARCLAYS-2026] | Economic threshold |
| Delivery at scale (profitable operator) | ~$4/delivery | [MANNA-2025] | Operational benchmark |
| Agriculture break-even acreage (owned platform) | ~980 acres/yr | [MU-EXT] | University research |
| BVLOS regulatory unlock | Part 108 expected 2026–27 | [FAA-108]; [DOT-OIG] | Regulatory milestone |
| Commercial Part 107 flights (US, 2024) | 16.6 million | [FAA-2024] | Market volume reference |
| Remote pilot rate (US) | $65/hr | Commercial operator surveys | Labor reference |

---

## 12. Sensitivity analysis

Three sensitivity sweeps are computed automatically alongside the base scenario.
Each varies one parameter ±30% while holding all others at the input values.

### 12.1 Labor cost sensitivity
Varies the human alternative rate from 70% to 130% of the input value.

**Purpose:** Shows how sensitive ROI is to local labor costs.
High sensitivity → deployment economics are driven by the local market, not the technology.
Low sensitivity → drone viability is robust regardless of labor cost variation.

**Most sensitive use cases:** inspection (helicopter), rural delivery.
**Least sensitive:** agriculture ground alternative (low human alternative rate).

### 12.2 Mission volume sensitivity
Varies annual missions from 50% to 200% of the input value.

**Purpose:** Shows the break-even dynamics and scale effects.
Reveals whether the deployment is a "volume play" (needs scale to be viable) or
a "per-mission win" (viable even at low volume).

**Key output:** at what volume does the verdict flip from CONDITIONAL to GO?

### 12.3 BVLOS unlock value
Computes a parallel scenario with `bvlos_status = authorized` if the base scenario is
currently VLOS-constrained or BVLOS-blocked.

**Purpose:** Quantifies the regulatory unlock value — how much additional annual savings
become accessible if BVLOS authorization is obtained.

This is expressed as:
```
bvlos_unlock_value = annual_savings[authorized] - annual_savings[current_status]
```

**Why this matters:** for many delivery and long-range inspection scenarios, BVLOS authorization
is the single most valuable regulatory change. This metric makes that argument numerically concrete
for investor or policy conversations — directly analogous to SAF mandate gap analysis in Sprint 1.

---

## 13. Deployment narrative generator

For each completed scenario, the model generates a structured executive narrative:

> "Based on your inputs, [use_case] drone deployment in a [geography] environment is [GO / CONDITIONAL / NOT VIABLE].
>
> The drone costs $[drone_DOC] per mission versus $[human_cost] for [human_alternative], a saving of
> [savings_pct]% per mission. At [annual_missions] missions per year, this translates to
> $[annual_savings] in annual savings.
>
> [If CONDITIONAL:] Deployment becomes fully viable above [break_even_volume] missions/year.
> At current volume, platform payback is estimated at [payback_months] months.
>
> [If NO-GO:] The binding constraint is: [binding_constraint].
> To make this deployment viable: [resolution_path].
>
> [Regulatory note if applicable:] BVLOS authorization [status]. Part 108 framework expected
> to provide a standardized permit pathway by [2026–27]. [FAA-108]"

This narrative is the primary output for client conversations and investment memos.

---

## 14. Known limitations

| Limitation | Severity | What to do about it |
|---|---|---|
| NDAA procurement restrictions not computed as cost | **High** | DJI / Chinese-origin platforms restricted for federal contracts and some utilities under NDAA §848. Adds 30–50% platform cost premium for NDAA-compliant alternatives (Skydio, Censys, Wingtra). Flag in UI for defense/utility clients |
| Sensor and data processing costs excluded | **High** | Inspection use cases rely on thermal, RGB, or LiDAR sensors ($2,000–$30,000) and post-flight analytics software. These can double or triple the effective mission cost. Add sensor tier input in v2 |
| Weather / seasonal availability not modeled | **High** | Wind >25 mph, precipitation, and low visibility ground most commercial rotary platforms. Operational availability typically 60–80% in continental US. Add availability factor multiplier |
| Single-pilot model (no multi-drone operations) | **Medium** | One pilot managing 2–4 drones in BVLOS delivery significantly improves economics. Not modeled in v1 |
| DaaS alternative not computed | **Medium** | Ownership model only. Drone-as-a-Service (per-mission contract) avoids upfront platform cost — relevant for low-volume scenarios flagged as CONDITIONAL |
| Delivery: single stop per mission assumed | **Medium** | Multi-drop delivery (2–4 packages per flight) improves unit economics for delivery use cases. Add multi-drop parameter |
| US regulatory framework only | **Medium** | EASA UAS Category A/B/C and U-Space framework (EU) not modeled. Add EU regulatory layer in v2 |
| Labor rate: single US reference | **Low** | International markets vary significantly. Labor multiplier partially addresses this; explicit market selection would improve accuracy |
| Battery lifecycle varies with conditions | **Low** | Temperature, storage, and discharge depth affect lifecycle. 250-cycle baseline is conservative for moderate climates |
| Noise and community acceptance not modeled | **Low** | Urban delivery faces community resistance independent of regulatory authorization. Soft constraint not currently flagged |

---

## 15. Worked example

**Scenario:** Wind turbine inspection, Professional platform, replacing rope access.

```
Inputs:
  use_case:         inspection
  human_alternative: rope_access
  platform:         professional ($20,000)
  mission_type:     point asset (wind turbine)
  mission_range:    1.0 km (on-site, VLOS)
  payload:          0.5 kg (thermal + RGB sensor)
  bvlos_status:     not required (VLOS on-site)
  annual_missions:  200 turbines/year
  geography:        rural
  labor_multiplier: standard (1.0×)

Step 1 — Platform checks:
  Payload:  0.5 kg < 2.7 kg (professional max) → OK
  Range:    1.0 km < 5.0 km (VLOS limit) → OK, BVLOS not required
  Regulatory: BVLOS not required → no regulatory constraint

Step 2 — Flight time (point asset):
  flight_time_hr   = 0.5 hr (hover inspection)
  setup_time_hr    = 0.5 hr
  mission_duration = 1.0 hr

Step 3 — Drone DOC per mission:
  Depreciation:  $20,000 / (3 × 200)       = $33.33
  Battery:       $450 / 250                 = $1.80
  Pilot:         $65 × 1.0 hr              = $65.00
  Maintenance:   ($20,000 × 0.15) / 200    = $15.00
  Insurance:     $2,000 / 200              = $10.00
  ─────────────────────────────────────────────────
  drone_DOC = $125.13 per mission

Step 4 — Human alternative (rope access):
  human_cost = $4,000 × 1.0 = $4,000 per turbine

Step 5 — Economic metrics:
  cost_savings_per_mission = $4,000 − $125  = $3,875
  cost_savings_pct         = 96.9%
  annual_savings           = $3,875 × 200   = $775,000

  break_even_volume        = $20,000 / $3,875 ≈ 6 missions
  platform_payback_months  = (6 / 200) × 12 ≈ 0.3 months (< 2 weeks)

Go/No-Go:
  → All constraint checks pass
  → Verdict: GO
  → Binding constraint: None

Narrative:
  "Wind turbine inspection drone deployment in a rural environment is VIABLE.
  The drone costs $125 per turbine versus $4,000 for rope access, a saving of 96.9%.
  At 200 inspections per year, this translates to $775,000 in annual savings.
  Platform cost is recovered after 6 missions (~2 weeks of operation).
  No BVLOS authorization required for on-site operations.
  This is the strongest economic case in the model: drone vs. helicopter and rope access
  show the highest ROI because the human alternative cost is driven by safety overhead,
  not just labor. The drone eliminates the safety overhead entirely."

Sensitivity sweeps:
  Labor cost +30% (rope access at $5,200/turbine):
    → savings increase to $5,075/mission → $1.015M/yr

  Volume at 100 missions/year (50%):
    → drone_DOC rises to $183/mission (higher depreciation and fixed costs per mission)
    → break-even: 5.2 missions → unchanged (savings decline proportionally)
    → annual savings: $3,817 × 100 = $381,700 → still GO

  BVLOS unlock value (not applicable — this scenario is VLOS):
    → If range extended to 5 km for linear infrastructure inspection:
    → BVLOS unlock value = $0 (already VLOS-viable at 5 km on light platform)
    → Note: for 10+ km missions (BVLOS required), unlock value becomes significant
```

---

## 16. Roadmap — what to develop next

**Step 3 (immediate value):** Add sensitivity sweep visualization.
Show how annual savings change as one input is varied from 50% to 200%, with the base scenario
highlighted. The BVLOS unlock value chart is the most powerful: it shows exactly what the
regulatory unlock is worth in dollar terms for the specific scenario.

**Step 4:** Add scenario comparison.
Run two deployments side-by-side (e.g., same operation: VLOS-only vs. BVLOS-authorized) and
display delta on all metrics. This is where the tool becomes most powerful as an investment
conversation tool — identical to Step 4 in Sprint 1.

**Step 5:** Add sensor cost tier.
A second cost dimension — payload sensor package — as a user-selectable input. This significantly
improves accuracy for inspection use cases and allows modeling of "when does the sensor pay for itself?"

**Step 6:** Add DaaS comparison mode.
For scenarios flagged as CONDITIONAL due to scale, automatically compute the DaaS alternative
(no platform acquisition, per-mission contract rate) and show the crossover volume where
ownership becomes preferable to contracting.

**Step 7:** Add NDAA compliance cost flag.
For scenarios involving federal or utility clients, apply a platform cost premium for NDAA-compliant
alternatives and show the delta vs. the base scenario.

**Step 8:** Add EU regulatory context.
Map the same constraint logic to EASA UAS Category A/B/C and U-Space framework for European
deployment scenarios. Same tool, second regulatory layer — doubles the addressable market.

---

## 17. What to say when challenged

> "This model doesn't produce certified answers — it shows what your deployment assumptions imply
> against industry-referenced cost benchmarks and current FAA regulatory requirements.
> Every cost coefficient is derived from published sources. Every constraint has a traceable basis.
> If you disagree with a specific number — say, the rope access rate or the battery lifecycle —
> we can open the derivation and discuss which published reference would be more appropriate
> for your specific market."

The model's credibility comes from **constraint traceability and structured comparison**,
not from pretending to predict operational outcomes exactly.

---

*Polaris — Deployment decision engine for commercial drone operations.*
*All cost coefficients are derived from published industry references.*
*Not a certified engineering or financial model. For structured decision support and early-stage exploration.*
