# MODEL.md — Polaris Scenario Engine

## 1. What Polaris is

Polaris is a **decision-support prototype** designed to translate uncertain early-stage assumptions in aerospace and climate transport into structured, benchmark-referenced insights.

It is built for:
- **Early-stage aerospace startups** — to structure their own thinking before facing investor questions
- **Investors and venture analysts** — to stress-test narratives and identify open questions
- **Strategy and innovation teams** — to compare scenario assumptions in a structured format

## 2. What Polaris is NOT

| It is NOT | Why this matters |
|---|---|
| A certified engineering model | Coefficients are heuristic, not validated against real fleet or test data |
| A financial forecasting tool | "Cost pressure" is an index, not a $ figure |
| A viability score engine | We deliberately removed any synthetic "go/no-go" score |
| An authoritative benchmark database | Benchmarks are illustrative references, not official standards |
| A predictive model | Outputs are implications of assumptions, not forecasts |

The key design decision: **we removed a synthetic viability score** because it was not grounded in a defensible methodology and was misleading when challenged. Instead, Polaris shows what assumptions *imply*, compared to *explicit reference points*, with *transparent caveats*.

---

## 3. Inputs

All inputs are scenario parameters set by the user. They represent assumptions, not measured values.

| Input | Scale | What it represents |
|---|---|---|
| `saf_share` | 0–100 (%) | Percentage of fuel mix assumed to be Sustainable Aviation Fuel |
| `hydrogen_readiness` | 0–100 (index) | Heuristic maturity signal for hydrogen propulsion or fuel pathway. 0 = no pathway, 100 = deployment-ready |
| `electricity_price` | 0–100 (index) | Relative electricity cost exposure. 0 = no dependency, 100 = high-cost grid dependency |
| `carbon_price` | 0–200 ($/tCO₂) | Policy carbon price assumption. Represents the strength of the regulatory environment |
| `demand_growth` | 0–100 (index) | Relative market demand growth signal. 0 = stagnant, 100 = fast-growing market |
| `concept` | categorical | Concept archetype: `regional`, `narrowbody`, or `drone`. Applies heuristic multipliers to baseline metrics |

**Important:** These are not calibrated inputs derived from measurement. They are assumption parameters — the user decides what they mean in their specific context.

---

## 4. Concept modifiers

Each concept archetype applies heuristic multipliers to adjust baseline metric levels. These are illustrative adjustments — not certified performance data.

| Concept | CAPEX pressure | Complexity | Adoption boost | Rationale |
|---|---|---|---|---|
| `regional` | 1.0× | 1.0× | 1.0× | Baseline reference |
| `narrowbody` | 1.1× | 1.2× | 0.9× | Higher certification burden, slower fleet turnover |
| `drone` (AAM) | 0.75× | 0.8× | 1.3× | Lower unit CAPEX, faster emerging market uptake assumed |

---

## 5. Output metrics

All outputs are **unit-less index values** unless explicitly noted. They are heuristic proxies — not real-world quantities.

### 5.1 Cost pressure index

**Lower = more favorable cost position**

- Base: 100 = pure kerosene fuel, no carbon policy, no SAF mandate
- SAF integration and higher hydrogen readiness reduce cost pressure
- High electricity price exposure and demand-driven scaling increase it
- Carbon pricing reduces cost pressure (reflects SAF/electrification incentive alignment)

```
cost_pressure = 100 × capex_factor
              − saf_share × 0.15
              − hydrogen_readiness × 0.05
              + electricity_price × 1.2
              − carbon_price × 0.03
              + demand_growth × 0.4
```

**Benchmark:** 100 (kerosene-only, no-policy baseline). Below 100 = more favorable position.

**⚠ Limitation:** The electricity_price coefficient (×1.2) dominates if the input is set high. The formula does not reflect real fuel cost structures — it is a relative pressure signal only.

---

### 5.2 Emissions intensity index

**Lower = better climate performance**

- Base: 100 = pure kerosene (reference for current commercial aviation)
- SAF blending is the primary decarbonization lever (coefficient −0.45 per % share)
- Hydrogen readiness provides an additional reduction (coefficient −0.18)
- Carbon pricing creates indirect discipline (coefficient −0.05)
- High electricity price is treated as a proxy for a carbon-intensive grid (coefficient +0.25)

```
emissions = 100
          − saf_share × 0.45
          − hydrogen_readiness × 0.18
          − carbon_price × 0.05
          + electricity_price × 0.25
```

**Benchmark:** 80 — illustrative CORSIA 2035 ambition proxy. A scenario below 50 would be broadly aligned with a Paris-compatible 2050 trajectory.

**⚠ Limitation:** The SAF coefficient (−0.45/%) is heuristic. Real SAF lifecycle emissions vary significantly by feedstock and production pathway. This index does not distinguish between lifecycle emissions sources.

---

### 5.3 Technical readiness risk index

**Lower = closer to deployment-ready**

- Base risk starts at 65 + concept complexity factor × 8
- Hydrogen readiness is the main de-risking lever (coefficient −0.35)
- SAF maturity provides a modest contribution (coefficient −0.05)
- Demand growth adds a small risk factor (supply-demand tension proxy)
- Bounded 0–100

```
technical_risk = 65
               − hydrogen_readiness × 0.35
               + demand_growth × 0.12
               + complexity_factor × 8
               − saf_share × 0.05
```

**Benchmark:** 30 — heuristic threshold. Below 30 = concept is sufficiently mature for serious commercial entry discussion. Above 60 = significant readiness gaps remain.

**⚠ Limitation:** The base risk of 65 is arbitrary. In practice, readiness thresholds depend heavily on regulatory environment, certification path, and specific technology TRL. This index should be treated as a discussion anchor, not a readiness assessment.

---

### 5.4 Adoption potential index

**Higher = stronger commercial traction signal**

- Combines SAF deployment signal, hydrogen readiness, and market demand growth
- Concept adoption boost factor applied (drone = 1.3×, narrowbody = 0.9×, regional = 1.0×)
- Bounded 0–100

```
adoption = (saf_share × 0.5 + hydrogen_readiness × 0.25 + demand_growth × 0.4) × adoption_boost
```

**Benchmark:** 50 — heuristic reference for strong commercial traction. Above 50 = assumptions are consistent with a commercially credible growth trajectory.

**⚠ Limitation:** The adoption index conflates technology readiness and market readiness into a single signal. In reality, these can diverge significantly (high tech readiness, low market demand — or vice versa).

---

### 5.5 Narrative strength index

**Higher = stronger investor-facing signal**

⚠ **This is a heuristic composite for framing discussions only. It is NOT a predictive metric and should never be presented as a validated signal.**

- Reflects how "investment narrative friendly" the assumption set is
- High SAF share, high hydrogen readiness, high carbon price, and high demand growth are positive signals
- High electricity price exposure is a negative signal

```
narrative = 45
           + saf_share × 0.15
           + hydrogen_readiness × 0.18
           − electricity_price × 0.4
           + carbon_price × 0.06
           + demand_growth × 0.1
```

**Benchmark:** 65 — heuristic reference for a compelling climate-tech investment narrative.

**⚠ Limitation:** This metric is the most arbitrary in the model. It should be used only to frame conversations about what makes a scenario narratively credible, not to claim that a scenario "is fundable."

---

## 6. Benchmarks

All benchmarks are **illustrative anchors** — not sourced from a single authoritative standard.

| Metric | Benchmark | Rationale |
|---|---|---|
| Cost pressure index | 100 | Kerosene-only baseline — natural anchor for cost comparison |
| Emissions intensity index | 80 | Directionally aligned with CORSIA 2035 carbon-neutral growth ambition |
| Technical readiness risk | 30 | Heuristic deployment-readiness threshold |
| Adoption potential | 50 | Midpoint reference for commercial traction |
| Narrative strength | 65 | Heuristic threshold for a credible investor narrative |

The gap column in the comparison table shows `(scenario − benchmark) / benchmark × 100`. A negative gap on a "lower is better" metric is favorable. A positive gap on a "higher is better" metric is favorable.

---

## 7. Interpretation and outputs

### Dynamic interpretation
The interpretation text is generated from actual benchmark readings — it is not hardcoded. It reflects which metrics are above or below their benchmarks for the specific scenario run.

### Headline
The headline is driven by a pattern-matching logic over the 5 benchmark readings. It identifies the dominant signal (e.g., "cost and readiness are the gating factors" when both are above benchmark) and avoids generic language.

### Strengths and watchouts
Both are derived dynamically from readings, and include actual computed values to make them actionable rather than generic.

### Radar chart
All axes point outward = more favorable. Three metrics are inverted for this display:
- "Cost position" = 200 − cost_pressure_index (higher outward = lower cost pressure)
- "Climate" = 100 − emissions_index (higher outward = lower emissions)
- "Readiness" = 100 − technical_risk_index (higher outward = lower risk)

### Benchmark bar chart
Shows scenario value vs benchmark reference for each metric. Bar color reflects benchmark reading: green (better), amber (near), red (gap). The dashed vertical line marks the benchmark reference value.

---

## 8. Known limitations and what to do about them

| Limitation | Severity | Suggested path forward |
|---|---|---|
| Coefficients are heuristic, not calibrated | High | Source coefficients from published lifecycle analyses (e.g., ICAO CORSIA lifecycle standards for SAF) |
| Benchmarks are not sourced | Medium | Add source citations per benchmark (CORSIA doc reference, IATA net-zero roadmap, etc.) |
| Narrative index is fully arbitrary | High | Either remove it, or replace with a structured qualitative checklist |
| Concept modifiers are arbitrary | Medium | Ground in real fleet data (e.g., ATR vs A320neo cost/complexity ratios) |
| Single-point outputs hide uncertainty | High | Add sensitivity sweeps or confidence bands as a next development step |
| Adoption index conflates supply and demand | Medium | Split into two independent signals: "technology readiness" and "market pull" |

---

## 9. Roadmap — how to make this more defensible

**Step 1 (near-term):** Add source citations to each benchmark. Even one credible reference per benchmark dramatically increases defensibility.

**Step 2:** Source SAF lifecycle emissions coefficients from ICAO CORSIA documentation or MIT FLEET model public outputs.

**Step 3:** Replace the narrative index with a structured qualitative checklist (e.g., "Does the scenario address: regulatory tailwind, infrastructure readiness, supply chain availability, policy support?").

**Step 4:** Add scenario comparison — run two scenarios side by side and show deltas. This is where the tool becomes most powerful in conversations.

**Step 5:** Add sensitivity analysis — show how outputs change when one input is varied while others are held constant. This exposes which assumptions actually drive the result.

---

## 10. What to say when challenged

> "This is not a model that produces true answers — it's a tool that makes your assumptions explicit and shows their implications against reference points. If you disagree with a benchmark or coefficient, we can adjust it and see how the picture changes. That's the point."

The model's credibility comes from **transparency**, not precision. Every number has a label, every benchmark has a rationale, and every output is explicitly framed as a proxy.

---

*Polaris — Assumption-to-implication translator for aerospace and climate transport.*
*Not a certified engineering or financial model. Intended for structured decision support and early-stage conversation.*
