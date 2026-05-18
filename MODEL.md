# MODEL.md — Polaris Scenario Engine v3

## 1. What Polaris is

Polaris is a **decision-support prototype** for aerospace and climate transport.
It translates user-defined assumptions into structured, benchmark-referenced implications grounded
in published aviation roadmap data.

Built for:
- **Early-stage aerospace startups** — to structure thinking before investor conversations
- **Investors and venture analysts** — to stress-test narratives against real reference trajectories
- **Strategy and innovation teams** — to compare scenario assumptions using published benchmarks

## 2. What Polaris is NOT

| It is NOT | Why this matters |
|---|---|
| A certified engineering model | Coefficients come from roadmap averages, not flight-test or fleet validation data |
| A financial forecasting tool | Cost outputs are $/seat proxies, not airline P&L figures |
| A viability score engine | No synthetic go/no-go score — outputs are physical quantities with explicit sources |
| An authoritative standard | Benchmarks are trajectory-derived references, not regulatory mandates |
| A predictive model | Outputs show what assumptions imply at a given year, not what will happen |

The design principle: **every coefficient has a source citation, every reference point has a derivation
methodology, and every displayed output is in real units (gCO₂/RPK, $/seat, %, TRL)**.

---

## 3. Primary sources

Every parameter in this model is traced to one of these published documents:

| Reference key | Full citation |
|---|---|
| **[IATA-CR]** | IATA, *Aviation Net-Zero CO2 Transition Pathways – Comparative Review*, April 2024 (co-published with ATAG, ICCT, MPP, IEA) |
| **[CAEP12]** | ICAO CAEP/12, *Environmental Trends in Aviation to 2050*, 2022 |
| **[CORSIA]** | ICAO, *CORSIA Default Life Cycle Emission Values for CORSIA Eligible Fuels*, 2022 (CORSIA Annex 16 Vol IV) |
| **[REFUELEU]** | Regulation (EU) 2023/2405 of the European Parliament and of the Council on ensuring a level playing field for sustainable air transport (ReFuelEU Aviation) |
| **[IATA-NZ]** | IATA, *Net-Zero Roadmap S2*, 2023 |
| **[ICAO-LTAG]** | ICAO, *Long-Term Aspirational Goal (LTAG) S2 and S3*, 2022 |
| **[ATAG-WP]** | ATAG, *Waypoint 2050 (2nd edition)*, 2021 |

---

## 4. Physical constants

| Constant | Value | Source |
|---|---|---|
| CO₂ combustion factor (Jet-A) | 3.16 kg CO₂/kg fuel | [CAEP12] p.28 — ICAO standard TTW emission factor |
| Jet-A density | 0.804 kg/L | ASTM D1655 / ICAO standard |
| CO₂ per litre of Jet-A | 2,540 g/L | Derived: 3.16 × 0.804 × 1,000 |
| Net calorific value | 43.2 MJ/kg | ICAO standard aviation fuel |
| Baseline year | 2019 | Pre-COVID reference year used by all major roadmaps |

These are the same physical constants used throughout [CAEP12], [CORSIA], and all major roadmaps.
Changing them would require a fundamental revision of the international accounting framework.

---
## 5. Inputs

All inputs are scenario parameters set by the user. They represent assumptions about a specific
development path, not measurements of an existing aircraft or operation.

### 5.1 Inputs currently exposed in the aviation demo

The current aviation dashboard exposes five user-controlled inputs:

- **Aircraft concept**
- **Target year**
- **SAF share (%)**
- **SAF type / pathway**
- **Technology efficiency scenario**

These are the inputs that most directly and visibly affect the climate, compliance, cost, and
readiness outputs shown in the dashboard.

### 5.2 Inputs currently fixed in the backend

Two additional assumptions remain in the backend but are not currently exposed in the aviation UI:

- **Demand growth scenario** — fixed to a mid-case value for now
- **Carbon price** — fixed to an EU ETS-style reference value for now

Reason:
these variables are still analytically relevant, but in the current aviation demo they do not yet
drive enough visible dashboard behavior to justify being shown as user-controlled levers.
They may be reintroduced later in a dedicated market / policy layer.

### 5.3 Aircraft concept

| Concept | Label | 2019 CO₂ intensity | Fuel intensity | Reference flight |
|---|---|---|---|---|
| `narrowbody` | A320 / B737-family | **88 gCO₂/RPK** | 0.0347 L/RPK | 165 seats × 800 km |
| `regional` | ATR-72 / E175-class | **110 gCO₂/RPK** | 0.0433 L/RPK | 75 seats × 500 km |
| `widebody` | A350 / B787-class | **72 gCO₂/RPK** | 0.0283 L/RPK | 280 seats × 8,000 km |

Source: [IATA-NZ] 2023 global commercial aviation mean; [CAEP12] 2022 fleet database.
Derivation: Global aviation consumed ~188 Mt fuel → 593 Mt CO₂ over ~8.7 trillion RPK in 2019,
giving a fleet-wide mean of ~88 gCO₂/RPK (TTW). Regional aircraft are ~25% higher due to shorter
cruise phases and lower seat density; widebody aircraft are ~18% more efficient at long range.

Fuel intensity (L/RPK) is derived directly: fuel_L_per_RPK = CO₂_g_per_RPK ÷ CO₂_g_per_L_Jet-A.

### 5.4 Target year

`2030`, `2035`, or `2050`.

Determines:
- the compounding period for the technology improvement factor
- the policy reference year
- the climate reference trajectory
- the pathway-specific SAF cost assumption
- the horizon-adjusted readiness proxy

### 5.5 SAF share (%)

Percentage of the total fuel mix assumed to be SAF. Range: 0–100%.

This is an assumption, not a forecast. The user decides what penetration level is relevant for
their scenario. The computation applies the SAF lifecycle saving proportionally to the fuel mix.

This input affects:
- CO₂ intensity
- CO₂ reduction
- policy gap
- scenario-level incremental SAF cost per seat
- EU ETS equivalent carbon cost per seat

### 5.6 SAF type / pathway

| SAF type | Label | WTW CO₂ saving | Base TRL | Price assumption ($/t) |
|---|---|---:|---:|---|
| `hefa` | Bio-SAF — HEFA | **75%** | 9 | 2030: 1100 · 2035: 900 · 2050: 750 |
| `mix` | Mixed blend — Bio-SAF + PtL | **82%** | 8 | 2030: 1700 · 2035: 1300 · 2050: 950 |
| `ptl` | Power-to-Liquid — e-fuel / Fischer-Tropsch | **90%** | 6 | 2030: 2500 · 2035: 1800 · 2050: 1100 |

**HEFA**: Average WTW saving of 75% vs Jet-A baseline (range: 55–85% depending on feedstock).
Commercially available, ASTM D7566 Annex 2 certified. Dominant SAF pathway today.

**PtL**: Produced from renewable-electricity hydrogen + captured CO₂. Near-zero lifecycle emissions
(85–95% saving; central estimate 90%). Commercial-scale deployment not yet achieved —
first plants expected 2027–2030.

**Mix**: Weighted average = 0.50 × 0.75 + 0.50 × 0.90 = 0.825 ≈ 0.82 lifecycle saving.
Represents the 2030–2040 transition period where HEFA remains dominant near-term but PtL
grows steadily.

In the current model, SAF pathway affects:
- lifecycle CO₂ reduction
- cost assumption
- technology readiness proxy

### 5.7 Technology efficiency scenario

| Scenario | Annual improvement | Source |
|---|---|---|
| `conservative` | **0.9%/yr** | [CAEP12] 2022, Fuel Scenario 2: 0.96%/yr from currently in-production aircraft |
| `moderate` | **1.3%/yr** | [CAEP12] Scenario 3 (1.16%/yr tech) + [IATA-CR] 2024 (0.2%/yr ATM ops) |
| `advanced` | **2.0%/yr** | [IATA-CR] 2024: ICCT Breakthrough (2.2%/yr from 2035); MPP PRU/ORE (2.0%/yr) |

This is the compound annual fleet-wide fuel burn improvement rate applied from 2019 to the
target year. It represents technology (new aircraft entering the fleet) plus operational
efficiency (ATM, load factors, single-engine taxi procedures).

The `advanced` scenario requires step-change aircraft concepts (open rotor, hybrid-electric,
boundary-layer ingestion) that are not yet certified for commercial service. Most roadmaps
assume these enter service no earlier than 2035.

### 5.8 Deferred inputs not currently exposed in the aviation UI

#### Demand growth scenario

| Scenario | CAGR (2019–2050) | Source |
|---|---|---|
| `low` | **2.1%/yr** | [IATA-CR] 2024, Table 3 — IEA Net-Zero 2050 (2023) |
| `mid` | **2.9%/yr** | [IATA-CR] 2024, Table 3 — IATA Net-Zero Roadmap S2 (2023) |
| `high` | **3.8%/yr** | [IATA-CR] 2024, Table 3 — ICAO LTAG S2/S3 (2022) |

**Important**: Demand growth does **not** affect the current per-RPK aviation dashboard metrics.
It remains in the backend as a contextual assumption and may be used later in a market-sizing
or sector-scale layer.

#### Carbon price ($/tCO₂)

Policy carbon price assumption. Used to compute:
- carbon cost per seat (on the fossil fuel fraction of the fuel mix)
- cost parity comparisons against EU ETS-style carbon pricing

Does **not** affect CO₂ intensity directly.

In the current aviation demo, this assumption remains fixed in the backend and is not exposed
as a visible input.

## 6. Computation methodology

### 6.1 CO₂ emissions intensity (gCO₂/RPK)

**Formula:**
```
tech_factor = (1 − annual_improvement_rate / 100) ^ years_from_2019
saf_factor  = 1 − (saf_share_pct / 100) × lca_saving
co2_intensity = baseline_2019_gco2_rpk × tech_factor × saf_factor
```

This formula applies two sequential reductions to the 2019 fleet-average baseline:

1. **Technology factor**: Compound annual fuel burn improvement, applied from 2019 to target year.
   This represents the fleet-level effect of new, more efficient aircraft replacing older ones,
   plus operational efficiency gains. Source: [CAEP12] 2022, Table 1-1 fuel burn scenarios.

2. **SAF factor**: Reduction in lifecycle CO₂ from the SAF blend. The fossil fuel fraction retains
   full Jet-A CO₂ intensity; the SAF fraction is reduced by the CORSIA WTW lifecycle saving.
   Source: [CORSIA] 2022 default lifecycle values.

**Units:** gCO₂/RPK, Tank-to-Wake with lifecycle adjustment for SAF share.
Non-CO₂ effects (contrails, NOx, water vapour) are excluded — CO₂ only.

**Benchmark derivation:**
Moderate and ambitious CO₂ intensity benchmarks for each target year are derived from roadmap
trajectory data. Starting from the 88 gCO₂/RPK 2019 baseline, applying the roadmaps' own
assumed technology improvement rates and SAF shares:

```
Moderate 2030 = 88 × (1−0.013)^11 × (1 − 0.06×0.75) ≈ 74 gCO₂/RPK
                                     ↑ ReFuelEU 6% SAF with HEFA 75% saving
Ambitious 2030 = 88 × (1−0.009)^11 × (1 − 0.21×0.80) ≈ 65 gCO₂/RPK
                                      ↑ ICAO LTAG S3 21% SAF target

Moderate 2050 = consistent with IATA S2: 465 Mt CO₂ / 21.55 T RPK ≈ 22 gCO₂/RPK
Ambitious 2050 = consistent with ATAG S3 / MPP ORE: ~8 gCO₂/RPK
```

Sources: [IATA-CR] 2024; [ICAO-LTAG] 2022; [ATAG-WP] 2021.

### 6.2 Incremental SAF cost per seat (USD)

This metric represents the **scenario-level extra cost per seat** associated with using SAF
instead of Jet-A on the selected reference flight.

It is not a pure fuel-unit premium. It is a **deployment-level economic impact**, meaning it
depends on how much SAF is used in the scenario.

### Methodology

The computation proceeds in four steps:

1. Compute total fuel per seat for the reference flight:

   fuel_per_seat_L = fuel_l_per_rpk × reference_range_km  
   fuel_per_seat_kg = fuel_per_seat_L × jet_a_density_kg_per_L  
   fuel_per_seat_t = fuel_per_seat_kg / 1000  

2. Compute SAF consumption per seat:

   saf_per_seat_t = fuel_per_seat_t × (saf_share_pct / 100)

3. Compute the fuel price premium:

   premium_per_tonne = max(0, SAF_price_pathway_year − jet_a_reference_price)

4. Compute incremental SAF cost per seat:

   incremental_saf_cost_per_seat = saf_per_seat_t × premium_per_tonne

### Interpretation

This metric depends on:
- aircraft fuel burn (via fuel_per_seat)
- reference flight length
- SAF share
- SAF pathway
- target year

It should be interpreted as:

> “How much additional cost per seat is introduced by using SAF at the assumed share in this scenario?”

### Pathway-specific SAF price assumptions

| Pathway | 2030 | 2035 | 2050 |
|---|---:|---:|---:|
| HEFA | $1,100/t | $900/t | $750/t |
| Mixed blend | $1,700/t | $1,300/t | $950/t |
| PtL | $2,500/t | $1,800/t | $1,100/t |

These values are simplified pathway anchors consistent with the direction of published IATA
roadmap ranges.

### Fossil fuel reference

Jet-A reference price: $700/tonne.

### Breakeven carbon price

The **breakeven carbon price** answers the question:

> At what carbon price does SAF become cost-neutral relative to fossil Jet-A?

This is a **marginal comparison**, not a scenario-level metric.

It is computed as:

breakeven = incremental_saf_cost_per_seat / co2_saved_per_seat

where:

co2_saved_per_seat = saf_per_seat_t × CO2_kg_per_kg_fuel × lca_saving

Because both cost and CO₂ savings scale with SAF share, the breakeven carbon price is primarily
driven by:
- SAF pathway
- target year
- fuel emissions factor

and does **not materially depend on SAF share**.

### EU ETS equivalent carbon cost per seat

This metric estimates the carbon cost per seat on the fossil fuel fraction of the scenario:

fossil_per_seat_t = fuel_per_seat_t × (1 − saf_share_pct / 100)  
eu_ets_cost = fossil_per_seat_t × CO2_kg_per_kg_fuel × EU_ETS_price  

This is used as an **economic parity reference** in the dashboard.

It should be interpreted as:

> “What carbon cost per seat would apply under EU ETS-style pricing for the remaining fossil fuel?”

Unlike climate or policy references, this is a **scenario-dependent comparison point**, not a
fixed external benchmark.

### 6.3 Policy compliance — SAF mandate

**Primary benchmark:** ReFuelEU Aviation (EU Regulation 2023/2405).
The binding minimum SAF blending obligation for all flights departing EU airports.

| Year | ReFuelEU minimum | ICAO LTAG S2 | ICAO LTAG S3 |
|---|---|---|---|
| 2030 | 6% | 13% | 21% |
| 2035 | 20% | 32% | 50% |
| 2050 | 70% | 72% | 98% |

Sources: [REFUELEU] EU 2023/2405; [ICAO-LTAG] 2022.

The gap is computed as: `scenario_SAF_share − ReFuelEU_target` (in percentage points, pp).
Positive gap = meeting or exceeding the mandate; negative = below mandate (regulatory risk
for EU-market operations).

**Important caveat:** ReFuelEU applies to EU-departing flights only. US and Asian markets
had no binding SAF mandates as of 2024, although voluntary commitments exist.

### 6.4 Technology readiness (TRL)

The dashboard displays a **horizon-adjusted readiness proxy** based on:

- the selected SAF pathway

- the selected target year

Base pathway TRLs:

| Pathway | Base TRL |

|---|---:|

| HEFA | 9 |

| Mixed blend | 8 |

| PtL | 6 |

Horizon adjustment applied in the current prototype:

| Target year | Adjustment |

|---|---:|

| 2030 | +0 |

| 2035 | +1 |

| 2050 | +2 |

Final displayed readiness is capped at TRL 9.

Examples:

- HEFA: 9 → 9 → 9

- Mix: 8 → 9 → 9

- PtL: 6 → 7 → 8

This should be interpreted as a **readiness proxy for decision support**, not as a literal

certification statement or deployment guarantee.

It is intended to reflect the idea that some pathways may plausibly mature over time even if

they are not fully commercial today.
---

## 7. Outputs and their units

All outputs are **real physical quantities, economic quantities, policy gaps, or readiness proxies** —
not synthetic index values.

| Output | Unit | What it measures |
|---|---|---|
| `co2_intensity_gco2_rpk` | gCO₂/RPK | Lifecycle-adjusted emissions intensity, Tank-to-Wake |
| `co2_reduction_from_2019_pct` | % | Percentage reduction vs 2019 fleet-average baseline |
| `saf_cost_premium_usd_per_seat` | USD/seat | Incremental SAF deployment cost per seat on the reference flight |
| `carbon_cost_per_seat_usd` | USD/seat | Carbon policy cost on the fossil fuel fraction |
| `total_cost_premium_per_seat_usd` | USD/seat | Incremental SAF cost + carbon cost combined |
| `saf_breakeven_carbon_price_usd_tco2` | $/tCO₂ | Carbon price at which the selected SAF pathway becomes cost-neutral on a marginal basis |
| `eu_ets_carbon_cost_per_seat` | USD/seat | Fossil-fuel carbon cost at EU ETS-style carbon pricing |
| `saf_trl` | 1–9 (integer) | Horizon-adjusted SAF pathway readiness proxy |
| `gap_vs_refueleu_pp` | percentage points | SAF share minus ReFuelEU mandate target |
| `gap_vs_icao_ltag_s2_pp` | percentage points | SAF share minus ICAO LTAG S2 target |
| `tech_deployment_risk` | Low / Low–Medium / Medium / High | Qualitative risk label for the aircraft technology pathway |
---

## 8. Key reference points

The dashboard compares scenario outputs against several different kinds of reference points:

- **Climate trajectory references**
- **Policy references**
- **Readiness references**
- **Economic parity references**

These are not all “benchmarks” in the same strict sense.
Some are external trajectory targets, some are mandates, and some are scenario-relative
economic comparison anchors.

| Metric | Reference | Type |
|---|---|---|
| CO₂ intensity — moderate | 74 / 55 / 22 gCO₂/RPK (2030/35/50) | Climate trajectory reference |
| CO₂ intensity — ambitious | 65 / 42 / 8 gCO₂/RPK (2030/35/50) | Climate trajectory reference |
| SAF mandate — primary | 6% / 20% / 70% (2030/35/50) | Policy reference |
| SAF mandate — secondary | 13% / 32% / 72% (2030/35/50) | Policy reference |
| SAF cost vs EU ETS | EU ETS equivalent carbon cost per seat | Economic parity reference |
| SAF TRL | TRL 9 | Readiness reference |

Gap convention:
- on **lower-is-better** metrics, negative gap is favorable
- on **higher-is-better** metrics, positive gap is favorable

---

## 9. Reference chart normalization

To enable visual comparison of metrics with different units on a single chart, each metric is
normalized to **% of its reference point** (100% = at reference).

| Metric | Normalization formula | Interpretation |
|---|---|---|
| CO₂ intensity | `(co2_intensity / moderate_reference) × 100` | Left of 100% = better |
| SAF compliance | `(saf_share / refueleu_target) × 100` | Right of 100% = better |
| SAF cost vs EU ETS | `(incremental_saf_cost / eu_ets_cost) × 100` | Left of 100% = cost-competitive |
| SAF TRL | `(saf_trl / 9) × 100` | Right of 100% = closer to full commercial readiness |

The dashed line at 100% should be interpreted as a **reference / parity line**, not always as a
homogeneous benchmark threshold.

---

## 10. Known limitations

| Limitation | Severity | What to do about it |
|---|---|---|
| Non-CO₂ effects excluded | **High** | Contrails, NOx, water vapour typically add 1.5–2× the CO₂-only climate impact. Add multiplier flag with range from Lee et al. (2021) |
| Fleet-level average baselines | High | Individual new-entry aircraft (A321XLR: ~20% better than A321ceo) will differ significantly from fleet averages. Add per-aircraft option |
| SAF price range not shown | Medium | Single median projection shown. Add scenario range ($1,000–$2,686 at 2030) as a sensitivity band |
| ReFuelEU scope limited to EU | Medium | Applies to EU-departing flights only. US/Asian market compliance gap not shown separately |
| Demand scenario currently hidden in the aviation UI | Medium | Demand remains in the backend as a fixed contextual assumption but does not currently drive visible aviation dashboard outputs |
| SAF lifecycle values are averages | Medium | HEFA from palm oil vs used cooking oil: 55–85% savings. The default (75%) is conservative waste-feedstock estimate |
| 2019 baseline is fleet-average | Low | Applies to new-entry concept aircraft that may start from a lower baseline. Add option to override baseline |
| No certification timeline | Low | TRL alone doesn't capture regulatory lead time. HEFA to ASTM certification took 5–7 years. Add flag |
| Readiness is a horizon-adjusted proxy | Medium | Displayed TRL evolves with target year for decision-support purposes; this is not a literal certification timeline |
| Economic parity reference is not a universal benchmark | Low | SAF cost vs EU ETS is a scenario-relative comparison anchor, not a fixed external benchmark in the same sense as policy or climate references |

---

## 11. Roadmap — what to develop next

**Step 3 (immediate value):** Add a sensitivity sweep.
Show how CO₂ intensity and SAF cost change as one input is varied ±20% while others are held constant.
This exposes which assumption actually drives the result — the single most useful addition
for investor conversations.

**Step 4:** Add scenario comparison.
Run two scenarios side-by-side (e.g., HEFA at 20% vs PtL at 20%) and show deltas on all metrics.
This is where the tool becomes most powerful as a conversation tool.

**Step 5:** Source non-CO₂ effects.
Use the Lee et al. (2021) effective radiative forcing multiplier (central estimate: 3.0×; range: 1.7–4.7×)
to offer an optional total climate metric in CO₂-equivalent (CO₂e/RPK).

**Step 6:** Expand aircraft concept to new-entry baseline.
Allow users to input a custom starting efficiency (e.g., 10–40% better than fleet average for a
next-generation aircraft) so the tool works for concept evaluation, not just fleet-level analysis.

---

## 12. What to say when challenged

> "This model doesn't produce true answers — it shows what your assumptions imply
> against published reference points from IATA, ICAO, and CORSIA.
> Every coefficient has a source. Every reference point has a derivation.
> If you disagree with a specific number, we can trace it back to the source document
> and discuss whether a different published value would be more appropriate."

The model's credibility comes from **traceability and structured comparison**, not from pretending
to predict the future exactly.

---

## 13. Formula derivation worked example

**Scenario:** Narrowbody, 2035 target, 30% HEFA SAF, moderate technology, $80/tCO₂ carbon price.

```
Baseline 2019:         88.0 gCO₂/RPK
Years:                 16 (2019→2035)
Tech factor:           (1 − 0.013)^16 = 0.811
SAF factor:            1 − (0.30 × 0.75) = 0.775
CO₂ intensity:         88.0 × 0.811 × 0.775 = 55.3 gCO₂/RPK
CO₂ reduction:         (1 − 55.3/88.0) × 100 = 37.2%
Moderate benchmark:    55 gCO₂/RPK → scenario at benchmark

Fuel per seat (ref flight: 165 seats × 800 km):
  fuel_L  = 0.0347 L/RPK × 800 km = 27.76 L/seat
  fuel_kg = 27.76 × 0.804 = 22.32 kg/seat
  fuel_t  = 0.02232 t/seat
  SAF fraction: 0.30 × 0.02232 = 0.006696 t SAF/seat
  Fossil:       0.70 × 0.02232 = 0.015624 t fossil/seat

SAF price 2035 (HEFA): $900/tonne
Premium:               $900 − $700 = $200/tonne
Incremental SAF cost/seat:
  SAF fraction = 0.30 × 0.02232 = 0.006696 t SAF/seat
  Incremental cost = 0.006696 × $200 = $1.34/seat

Fossil CO₂/seat:       0.015624 × 3.16 = 0.0494 tCO₂/seat
Carbon cost/seat ($80): 0.0494 × $80 = $3.95/seat

Breakeven carbon price:
  CO₂ saved = 0.006696 × 3.16 × 0.75 = 0.01587 tCO₂/seat
  Breakeven = $1.34 / 0.01587 ≈ $84/tCO₂

ReFuelEU target 2035: 20% → scenario at 30% → gap: +10pp (compliant)
Readiness proxy 2035: base TRL 9 + horizon adjustment capped at 9 → TRL 9
```

---

*Polaris — Assumption-to-implication translator for aerospace and climate transport.*
*All formulas use sourced physical constants and published roadmap data.*
*Not a certified engineering or financial model. For structured decision support and early-stage exploration.*
