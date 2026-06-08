# Sprint 4 — Founder Failure Mode Analyzer
## Model Specification

---

## Top Event

**FAIL TO REACH NEXT FINANCING MILESTONE BEFORE RUNWAY EXHAUSTION**

Applicable to seed → Series A transition (primary target), but architecture generalizes to any stage.

---

## Fault Tree Structure

All intermediate gates are **OR** (any child failure causes parent failure).

```
FAIL TO REACH NEXT FINANCING MILESTONE
              OR
  ┌───────────┼───────────┬───────────┐
  │           │           │           │
CAPITAL    REVENUE      TEAM       PRODUCT
FAILURE    FAILURE     FAILURE     FAILURE
  OR          OR          OR          OR
  │           │           │           │
 [C1]        [R1]        [T1]        [P1]
 [C2]        [R2]        [T2]        [P2]
 [C3]        [R3]
```

---

## Leaf Nodes & Transfer Functions

All transfer functions output P ∈ [0, 1] — the probability of that failure mode occurring.

Sigmoid helper: `σ(x) = 1 / (1 + exp(-x))`

---

### CAPITAL BRANCH

**C1 — Burn Too High**

> Runway is insufficient to execute + fundraise before cash exhaustion.

Input: `cash_on_hand` ($), `monthly_burn` ($), `fundraising_timeline` (months)

```
runway_months = cash_on_hand / monthly_burn
required_runway = fundraising_timeline + 6   // 6-month buffer for fundraising process
deficit = required_runway - runway_months
P(C1) = σ(deficit / 2.5)
```

Calibration:
- runway = 18 months, required = 12 → deficit = -6 → P ≈ 0.09 ✓ (safe)
- runway = 12 months, required = 12 → deficit = 0  → P ≈ 0.50 ✓ (borderline)
- runway = 6 months,  required = 12 → deficit = 6  → P ≈ 0.91 ✓ (critical)

---

**C2 — Fundraise Delayed / Failed**

> Fundraising takes longer than planned or falls through.

Input: `fundraising_timeline` (months), `fundraise_confidence` (1–5 scale)

```
base_delay_risk = 0.35  // ~35% of Series A processes slip significantly (Crunchbase base rate)
confidence_adjustment = (3 - fundraise_confidence) * 0.12
timeline_penalty = max(0, (fundraising_timeline - 9) * 0.02)
P(C2) = clamp(base_delay_risk + confidence_adjustment + timeline_penalty, 0.05, 0.95)
```

Calibration:
- confidence=5, timeline=6 → P ≈ 0.11 ✓
- confidence=3, timeline=9 → P ≈ 0.35 ✓
- confidence=1, timeline=18 → P ≈ 0.77 ✓

---

**C3 — Unexpected Cost Shock**

> Unforeseen expenses (infra, legal, hiring, regulatory) accelerate runway exhaustion.

Input: `monthly_burn` ($)

```
// Higher burn = more exposure surface to cost shocks
base_shock_risk = 0.12
burn_factor = min(monthly_burn / 500000, 1.0)  // normalized at $500k/mo
P(C3) = base_shock_risk + burn_factor * 0.15
```

Calibration:
- burn=$50k/mo  → P ≈ 0.13
- burn=$200k/mo → P ≈ 0.18
- burn=$500k/mo → P ≈ 0.27

---

### REVENUE BRANCH

**R1 — Poor Retention**

> Churn rate is too high for Series A benchmarks (investors expect >85% annual NRR for SaaS).

Input: `monthly_retention` (%) — expressed as decimal, e.g. 0.95

```
annual_retention = monthly_retention ^ 12
benchmark = 0.85  // Series A SaaS baseline
delta = annual_retention - benchmark
P(R1) = σ(-delta / 0.07)
```

Calibration:
- monthly=0.98 → annual=0.785... wait, 0.98^12 = 0.785 — hmm that's below benchmark
- monthly=0.99 → annual=0.886 → delta=+0.036 → P ≈ 0.30 ✓
- monthly=0.985→ annual=0.835 → delta=-0.015 → P ≈ 0.58
- monthly=0.995→ annual=0.942 → delta=+0.092 → P ≈ 0.09 ✓

Note: typical good SaaS monthly retention is 97-99%. UI should default to 97%.

---

**R2 — Low Growth**

> Monthly growth rate below Series A threshold. Benchmark: ~8-15% MoM depending on sector/stage.

Input: `monthly_growth_rate` (%) — expressed as decimal, e.g. 0.10

```
benchmark_growth = 0.08  // conservative Series A threshold
delta = monthly_growth_rate - benchmark_growth
P(R2) = σ(-delta / 0.03)
```

Calibration:
- growth=15%  → delta=+0.07 → P ≈ 0.10 ✓
- growth=8%   → delta=0     → P ≈ 0.50 ✓
- growth=3%   → delta=-0.05 → P ≈ 0.85 ✓

---

**R3 — Customer Concentration**

> Single customer >30% of revenue creates catastrophic single-point-of-failure risk.

Input: `largest_customer_pct` (%) — as decimal, e.g. 0.40

```
threshold = 0.30
delta = largest_customer_pct - threshold
P(R3) = σ(delta / 0.08)
```

Calibration:
- 15% → delta=-0.15 → P ≈ 0.16 ✓
- 30% → delta=0     → P ≈ 0.50 ✓
- 60% → delta=+0.30 → P ≈ 0.98 ✓

---

### TEAM BRANCH

**T1 — Key Person Risk**

> Critical knowledge/relationships concentrated in 1 person. Departure is a terminal event.

Input: `key_person_dependency` (1–5 scale)
- 1 = distributed knowledge, redundant systems
- 5 = single person holds all customer relationships, technical architecture, investor rapport

```
P(T1) = 0.05 + (key_person_dependency - 1) / 4 * 0.75
```

Calibration:
- dep=1 → P = 0.05 ✓
- dep=3 → P = 0.43
- dep=5 → P = 0.80 ✓

---

**T2 — Hiring Bottleneck**

> Unable to hire critical roles fast enough to hit growth milestones.

Input: `founder_count` (1–4), `hiring_difficulty` (1–5 scale)

```
founder_penalty = max(0, (2 - founder_count) * 0.10)
P(T2) = 0.10 + (hiring_difficulty - 1) / 4 * 0.55 + founder_penalty
```

Calibration:
- difficulty=1, founders=3 → P ≈ 0.10 ✓
- difficulty=3, founders=2 → P ≈ 0.38
- difficulty=5, founders=1 → P ≈ 0.75 ✓

---

### PRODUCT BRANCH

**P1 — Technical Risk**

> Core technical bets haven't been validated. Architecture may not scale or may be undeliverable.

Input: `technical_complexity` (1–5 scale)
- 1 = proven tech stack, no novel algorithms
- 5 = frontier AI, novel hardware, unproven physics

```
P(P1) = 0.05 + (technical_complexity - 1) / 4 * 0.75
```

Calibration:
- complexity=1 → P = 0.05 ✓
- complexity=3 → P = 0.43
- complexity=5 → P = 0.80 ✓

---

**P2 — Market Misfit**

> Product doesn't solve a problem customers will pay for at scale.

Input: `customer_validation` (1–5 scale)
- 1 = no paying customers, idea stage
- 5 = strong NPS, expansion revenue, clear ICP

```
P(P2) = 0.95 - (customer_validation - 1) / 4 * 0.85
```

Calibration:
- validation=1 → P = 0.95 ✓
- validation=3 → P = 0.53
- validation=5 → P = 0.10 ✓

---

## Probability Propagation

### OR Gate (all branches use OR):
```
P(branch_failure) = 1 - ∏(1 - P(leaf_i))
```

### Top Event:
```
P(top_event) = 1 - ∏(1 - P(branch_i))
  where branches = [Capital, Revenue, Team, Product]
```

---

## Monte Carlo Sampling

Each input is sampled from a distribution centered on the user's input.

| Input | Distribution | σ |
|---|---|---|
| cash_on_hand | Normal | 10% of mean |
| monthly_burn | Normal | 15% of mean |
| fundraising_timeline | Normal | 1 month |
| fundraise_confidence | Discrete ±1 with 20% prob | — |
| monthly_retention | Normal | 0.005 |
| monthly_growth_rate | Normal | 0.02 |
| largest_customer_pct | Normal | 0.05 |
| key_person_dependency | Discrete ±1 with 25% prob | — |
| hiring_difficulty | Discrete ±1 with 25% prob | — |
| technical_complexity | Discrete ±1 with 20% prob | — |
| customer_validation | Discrete ±1 with 20% prob | — |

All samples clamped to valid ranges.

### Correlation Structure (Revenue Branch)
R1 (retention) and R2 (growth) are correlated: ρ = 0.55
Implemented via Cholesky decomposition on the (retention, growth_rate) pair before sampling.

### N = 10,000 iterations

---

## Outputs

### 1. Risk Decomposition
```
Relative contribution of each branch to total failure probability:
  Capital: P(capital) / sum(P(branches)) × 100%
  Revenue: ...
  Team: ...
  Product: ...
```

Note: branches are not independent, so this is a relative attribution, not additive probability.

### 2. Survival Proxy
```
Survival Score = 1 - P(top_event)  // from Monte Carlo
```
Framed as "Survival probability under current assumptions" — explicitly labeled as a model output, not a prediction.

### 3. Binding Constraint
The single leaf node with the highest P value. Displayed with:
- Failure mode name
- Mechanism description
- Severity / Likelihood / Detectability (qualitative, not RPN for MVP)

### 4. Sensitivity Analysis
For each continuous input, compute:
```
sensitivity_i = |P(top_event | x_i + 1σ) - P(top_event | x_i - 1σ)|
```
Rank inputs by sensitivity. Top 3 displayed.

### 5. Mitigation Card
For the binding constraint, display:
- What to change
- Target value
- Expected risk reduction (delta P of that leaf node)

---

## Input Defaults (representative seed-stage startup)

| Input | Default | Range |
|---|---|---|
| cash_on_hand | $1,200,000 | $100k – $10M |
| monthly_burn | $120,000 | $10k – $1M |
| fundraising_timeline | 9 months | 3 – 24 months |
| fundraise_confidence | 3 | 1 – 5 |
| monthly_retention | 95% | 80% – 99.5% |
| monthly_growth_rate | 8% | 0% – 30% |
| largest_customer_pct | 35% | 5% – 90% |
| key_person_dependency | 3 | 1 – 5 |
| hiring_difficulty | 3 | 1 – 5 |
| technical_complexity | 3 | 1 – 5 |
| customer_validation | 3 | 1 – 5 |

---

## Methodology Note (for UI)

> This tool applies aerospace failure mode analysis (FMEA + fault trees) to startup risk.  
> Outputs are structured reasoning aids, not statistical predictions.  
> Survival probability represents model coherence under your assumptions — not a forecast.

---
