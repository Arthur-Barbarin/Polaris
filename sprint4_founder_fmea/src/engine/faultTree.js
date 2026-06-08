// ============================================================
// Founder Failure Mode Analyzer — Fault Tree Engine
// Aerospace FMEA + fault tree methodology applied to startups
// ============================================================

const sigmoid = (x) => 1 / (1 + Math.exp(-x))
const clamp = (val, min, max) => Math.max(min, Math.min(max, val))

// ─────────────────────────────────────────────
// TRANSFER FUNCTIONS — inputs → leaf P(failure)
// ─────────────────────────────────────────────

export function computeLeafProbabilities(inputs) {
  const {
    cash_on_hand,
    monthly_burn,
    current_mrr = 0,
    fundraising_timeline,
    fundraise_confidence,
    investor_traction,       // replaces founder_count (1=no interest, 5=soft commits)
    monthly_retention,
    monthly_growth_rate,
    largest_customer_pct,
    key_person_dependency,
    hiring_difficulty,
    technical_complexity,
    customer_validation,
  } = inputs

  // ── CAPITAL ──────────────────────────────────
  // Net burn = gross burn minus current MRR (revenue offsets cash outflow)
  const raw_net_burn = monthly_burn - current_mrr
  // When cash-flow positive (MRR ≥ burn), capital risk is minimal — C1 floors naturally.
  // When burning cash, runway = cash / net_burn; sigmoid is smooth as net_burn → 0⁺.
  const required_runway = fundraising_timeline + 3
  const C1 = raw_net_burn <= 0
    ? 0.02  // profitable: no runway risk
    : clamp(sigmoid((required_runway - cash_on_hand / raw_net_burn) / 2.5), 0.02, 0.98)

  // investor_traction directly reduces fundraise delay risk
  // traction=5 (soft commits) → −0.24; traction=1 (no interest) → +0.16
  const base_delay    = 0.35
  const conf_adj      = (3 - fundraise_confidence) * 0.10
  const timeline_pen  = Math.max(0, (fundraising_timeline - 9) * 0.02)
  const traction_adj  = (3 - investor_traction) * 0.08
  const C2 = clamp(base_delay + conf_adj + timeline_pen + traction_adj, 0.05, 0.90)

  // ── REVENUE ──────────────────────────────────
  // Benchmark: 80% annual NRR (Series A floor, not aspirational target)
  // sigma=0.05: 99% monthly (88.6% annual) → P≈0.15 (green); 97% monthly (69% annual) → P≈0.87
  const annual_retention = Math.pow(monthly_retention, 12)
  const ret_delta = annual_retention - 0.80
  const R1 = clamp(sigmoid(-ret_delta / 0.05), 0.02, 0.98)

  // sigma=0.06: being 2pp above benchmark → moderate, not high risk
  // 10% growth → P≈0.42; 15% growth → P≈0.22; 5% growth → P≈0.70
  const growth_delta = monthly_growth_rate - 0.08
  const R2 = clamp(sigmoid(-growth_delta / 0.06), 0.02, 0.98)

  const conc_delta = largest_customer_pct - 0.30
  const R3 = clamp(sigmoid(conc_delta / 0.08), 0.02, 0.98)

  // ── TEAM ─────────────────────────────────────
  const T1 = clamp(0.05 + (key_person_dependency - 1) / 4 * 0.75, 0.05, 0.90)
  const T2 = clamp(0.10 + (hiring_difficulty - 1) / 4 * 0.55, 0.05, 0.85)

  // ── PRODUCT ──────────────────────────────────
  const P1 = clamp(0.05 + (technical_complexity - 1) / 4 * 0.75, 0.05, 0.90)
  const P2 = clamp(0.95 - (customer_validation - 1) / 4 * 0.85, 0.05, 0.95)

  return { C1, C2, R1, R2, R3, T1, T2, P1, P2 }
}

// ─────────────────────────────────────────────
// OR GATE PROPAGATION
// P(branch) = 1 - ∏(1 - P(leaf_i))
// ─────────────────────────────────────────────

export function propagateTree(leaves) {
  const { C1, C2, R1, R2, R3, T1, T2, P1, P2 } = leaves

  const capital  = 1 - (1 - C1) * (1 - C2)
  const revenue  = 1 - (1 - R1) * (1 - R2) * (1 - R3)
  const team     = 1 - (1 - T1) * (1 - T2)
  const product  = 1 - (1 - P1) * (1 - P2)
  const top      = 1 - (1 - capital) * (1 - revenue) * (1 - team) * (1 - product)

  return { capital, revenue, team, product, top }
}

// ─────────────────────────────────────────────
// RESILIENCE SCORE
// Weighted mean of branch failure probabilities.
// More calibrated than OR-product (which saturates to ~1 quickly).
// Weights: capital + revenue weighted higher (more predictive of Series A).
// Score: 1 = zero risk, 0 = maximum risk.
// ─────────────────────────────────────────────

export function computeResilienceScore(branchProbs) {
  const { capital, revenue, team, product } = branchProbs
  const failureIndex = 0.30 * capital + 0.30 * revenue + 0.20 * team + 0.20 * product
  return 1 - failureIndex
}

// ─────────────────────────────────────────────
// MONTE CARLO ENGINE — 10,000 iterations
// ─────────────────────────────────────────────

function randNormal(mean, std) {
  // Box-Muller transform
  const u1 = Math.random()
  const u2 = Math.random()
  const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2)
  return mean + std * z
}

function sampleInputs(base) {
  // Correlated sampling for (monthly_retention, monthly_growth_rate)
  // ρ = 0.55 via Cholesky: L = [[1,0],[0.55, sqrt(1-0.55^2)]]
  const z1 = randNormal(0, 1)
  const z2 = randNormal(0, 1)
  const rho = 0.55
  const corr_growth = rho * z1 + Math.sqrt(1 - rho * rho) * z2

  return {
    cash_on_hand:          clamp(randNormal(base.cash_on_hand, base.cash_on_hand * 0.10), 50000, 1e8),
    monthly_burn:          clamp(randNormal(base.monthly_burn, base.monthly_burn * 0.15), 5000, 2e6),
    fundraising_timeline:  clamp(randNormal(base.fundraising_timeline, 1.0), 2, 30),
    fundraise_confidence:  clamp(Math.round(base.fundraise_confidence + (Math.random() < 0.2 ? (Math.random() < 0.5 ? 1 : -1) : 0)), 1, 5),
    investor_traction:     clamp(Math.round(base.investor_traction + (Math.random() < 0.2 ? (Math.random() < 0.5 ? 1 : -1) : 0)), 1, 5),
    monthly_retention:     clamp(base.monthly_retention + z1 * 0.005, 0.50, 0.999),
    monthly_growth_rate:   clamp(base.monthly_growth_rate + corr_growth * 0.02, 0, 0.60),
    largest_customer_pct:  clamp(randNormal(base.largest_customer_pct, 0.05), 0.01, 0.99),
    key_person_dependency: clamp(Math.round(base.key_person_dependency + (Math.random() < 0.25 ? (Math.random() < 0.5 ? 1 : -1) : 0)), 1, 5),
    hiring_difficulty:     clamp(Math.round(base.hiring_difficulty + (Math.random() < 0.25 ? (Math.random() < 0.5 ? 1 : -1) : 0)), 1, 5),
    technical_complexity:  clamp(Math.round(base.technical_complexity + (Math.random() < 0.20 ? (Math.random() < 0.5 ? 1 : -1) : 0)), 1, 5),
    customer_validation:   clamp(Math.round(base.customer_validation + (Math.random() < 0.20 ? (Math.random() < 0.5 ? 1 : -1) : 0)), 1, 5),
  }
}

// Proper uncertainty propagation:
// For each simulation, sample inputs from their uncertainty distributions,
// then compute P(branch failure) deterministically.
// Report mean P across simulations — this is E[P(failure)] under input uncertainty.
export function runMonteCarlo(baseInputs, N = 10000) {
  let capitalSum = 0, revenueSum = 0, teamSum = 0, productSum = 0, resilienceSum = 0

  for (let i = 0; i < N; i++) {
    const sampled = sampleInputs(baseInputs)
    const leaves  = computeLeafProbabilities(sampled)
    const probs   = propagateTree(leaves)
    const res     = computeResilienceScore(probs)

    capitalSum    += probs.capital
    revenueSum    += probs.revenue
    teamSum       += probs.team
    productSum    += probs.product
    resilienceSum += res
  }

  return {
    capital:    capitalSum    / N,
    revenue:    revenueSum    / N,
    team:       teamSum       / N,
    product:    productSum    / N,
    resilience: resilienceSum / N,
  }
}

// ─────────────────────────────────────────────
// SENSITIVITY ANALYSIS
// Vary each continuous input ±1σ, measure Δ Resilience Score
// (NOT top-event probability — that saturates to 99% and gives useless <1pp deltas)
// ─────────────────────────────────────────────

const CONTINUOUS_INPUTS = [
  { key: 'cash_on_hand',         label: 'Cash on Hand',           sigma: (v) => v * 0.25, direction: 'lower is worse' },
  { key: 'monthly_burn',         label: 'Monthly Burn',           sigma: (v) => v * 0.25, direction: 'higher is worse' },
  { key: 'monthly_retention',    label: 'Monthly Retention',      sigma: () => 0.01,       direction: 'lower is worse' },
  { key: 'monthly_growth_rate',  label: 'Monthly Growth Rate',    sigma: () => 0.04,       direction: 'lower is worse' },
  { key: 'largest_customer_pct', label: 'Customer Concentration', sigma: () => 0.15,       direction: 'higher is worse' },
  { key: 'fundraising_timeline', label: 'Fundraising Timeline',   sigma: () => 3,          direction: 'higher is worse' },
]

export function computeSensitivity(baseInputs) {
  const baseScore = computeResilienceScore(propagateTree(computeLeafProbabilities(baseInputs)))

  return CONTINUOUS_INPUTS.map(({ key, label, sigma, direction }) => {
    const s = sigma(baseInputs[key])

    const inputsUp   = { ...baseInputs, [key]: baseInputs[key] + s }
    const inputsDown = { ...baseInputs, [key]: baseInputs[key] - s }

    const scoreUp   = computeResilienceScore(propagateTree(computeLeafProbabilities(inputsUp)))
    const scoreDown = computeResilienceScore(propagateTree(computeLeafProbabilities(inputsDown)))

    // delta = full swing from worst to best direction
    const delta = Math.abs(scoreUp - scoreDown)

    return { key, label, delta, direction, baseScore }
  }).sort((a, b) => b.delta - a.delta)
}

// ─────────────────────────────────────────────
// BINDING CONSTRAINT
// Single leaf node with highest failure probability
// ─────────────────────────────────────────────

export const LEAF_META = {
  C1: {
    name: 'Runway Exhaustion',
    branch: 'Capital',
    mechanism: 'Cash depletes before milestone is reached',
    mitigation: 'Extend runway: cut burn or raise a bridge',
    mitigationTarget: 'Increase runway to ≥18 months',
  },
  C2: {
    name: 'Fundraise Delayed',
    branch: 'Capital',
    mechanism: 'Raise takes longer or falls through; extends time-to-close',
    mitigation: 'Start process earlier, increase investor pipeline',
    mitigationTarget: 'Begin fundraising 12+ months before runway end',
  },
  R1: {
    name: 'Poor Retention',
    branch: 'Revenue',
    mechanism: 'Churn erodes revenue base faster than new bookings can offset',
    mitigation: 'Identify top-3 churn reasons; fix onboarding and activation',
    mitigationTarget: 'Reach >85% annual NRR before Series A process',
  },
  R2: {
    name: 'Growth Stall',
    branch: 'Revenue',
    mechanism: 'MoM growth below Series A benchmark (~8%); story doesn\'t compound',
    mitigation: 'Identify bottleneck in acquisition funnel; test new channels',
    mitigationTarget: 'Sustain ≥10% MoM for 6 consecutive months',
  },
  R3: {
    name: 'Customer Concentration',
    branch: 'Revenue',
    mechanism: 'Single customer exit causes immediate revenue collapse and runway crisis',
    mitigation: 'Diversify: no single customer >25% revenue before raise',
    mitigationTarget: 'Reduce top customer from current % to <25% of MRR',
  },
  T1: {
    name: 'Key Person Risk',
    branch: 'Team',
    mechanism: 'Critical knowledge, relationships, or execution concentrated in one person',
    mitigation: 'Document systems; distribute customer relationships across team',
    mitigationTarget: 'No single person holds >60% of critical dependencies',
  },
  T2: {
    name: 'Hiring Bottleneck',
    branch: 'Team',
    mechanism: 'Unable to staff critical roles fast enough to hit growth milestones',
    mitigation: 'Build talent pipeline 6 months ahead; use advisors as bridge',
    mitigationTarget: 'Reduce time-to-hire for critical roles to <45 days',
  },
  P1: {
    name: 'Technical Risk',
    branch: 'Product',
    mechanism: 'Core technical assumptions haven\'t been validated at scale',
    mitigation: 'De-risk by validating hardest technical assumptions first',
    mitigationTarget: 'Reach TRL 6+ on critical technical components',
  },
  P2: {
    name: 'Market Misfit',
    branch: 'Product',
    mechanism: 'Product doesn\'t solve a problem customers pay for repeatedly',
    mitigation: 'Intensive customer discovery; tighten ICP definition',
    mitigationTarget: 'Achieve NPS >30 and clear expansion revenue signal',
  },
}

export function findBindingConstraint(leaves) {
  return Object.entries(leaves)
    .map(([key, prob]) => ({ key, prob, meta: LEAF_META[key] }))
    .sort((a, b) => b.prob - a.prob)[0]
}

// ─────────────────────────────────────────────
// RISK DECOMPOSITION
// Relative branch contributions (normalized)
// ─────────────────────────────────────────────

export function computeRiskDecomposition(branchProbs) {
  const { capital, revenue, team, product } = branchProbs
  const total = capital + revenue + team + product
  return {
    capital: capital / total,
    revenue: revenue / total,
    team:    team / total,
    product: product / total,
    total,
  }
}

// ─────────────────────────────────────────────
// TEMPORAL TRAJECTORY
// Projects risk forward month-by-month.
// Dynamic: cash depletes at net burn (gross - MRR); MRR compounds monthly;
// concentration risk shrinks as MRR grows (largest customer $ is fixed).
// Static: retention, growth rate, team, product held constant.
// ─────────────────────────────────────────────

export function computeTrajectory(baseInputs, months = 18) {
  const points = []
  const mrr0 = baseInputs.current_mrr || 0
  const g    = baseInputs.monthly_growth_rate || 0
  let cash   = baseInputs.cash_on_hand

  // Largest customer in absolute $ — stays fixed as MRR grows, so concentration drops
  // Only meaningful when mrr0 > 0; otherwise fall back to fixed ratio
  const largestCustomerAbs = mrr0 > 0
    ? baseInputs.largest_customer_pct * mrr0
    : null

  for (let m = 0; m <= months; m++) {
    // MRR compounds with growth rate each month
    const mrr_m      = mrr0 * Math.pow(1 + g, m)
    const net_burn_m = Math.max(0, baseInputs.monthly_burn - mrr_m)

    // Concentration shrinks as MRR grows (same absolute $ from largest customer)
    const concentration_m = largestCustomerAbs !== null && mrr_m > 0
      ? Math.min(0.99, largestCustomerAbs / mrr_m)
      : baseInputs.largest_customer_pct

    const projected = {
      ...baseInputs,
      cash_on_hand:         Math.max(0, cash),
      current_mrr:          mrr_m,
      largest_customer_pct: concentration_m,
    }
    const leaves      = computeLeafProbabilities(projected)
    const branchProbs = propagateTree(leaves)
    const resilience  = computeResilienceScore(branchProbs)

    points.push({
      month: m,
      resilience,
      capital:  branchProbs.capital,
      revenue:  branchProbs.revenue,
      team:     branchProbs.team,
      product:  branchProbs.product,
      runway:   net_burn_m > 0 ? cash / net_burn_m : Infinity,
      mrr:      mrr_m,
      net_burn: net_burn_m,
      C1:       leaves.C1,
    })

    // Deplete cash for next month
    cash = Math.max(0, cash - net_burn_m)
  }

  // Key milestones
  const runwayExhausted    = points.find(p => p.runway <= 0)
  const capitalCritical    = points.find(p => p.capital >= 0.85)
  const resilienceCritical = points.find(p => p.resilience <= 0.20)

  return {
    points,
    milestones: {
      runwayExhausted:    runwayExhausted    ? runwayExhausted.month    : null,
      capitalCritical:    capitalCritical    ? capitalCritical.month    : null,
      resilienceCritical: resilienceCritical ? resilienceCritical.month : null,
    }
  }
}

// ─────────────────────────────────────────────
// DEFAULTS
// ─────────────────────────────────────────────

// Defaults represent a seed-stage startup doing reasonably well:
// $1.8M cash, $120k/mo burn → 15 months runway
// 99% monthly retention → ~88.6% annual NRR (above 80% floor benchmark) → R1 shows green
// 10% MoM growth (above 8% benchmark)
// 25% top customer (below 30% concentration threshold)
// investor_traction=3 (neutral — some conversations, no commitments)
export const DEFAULT_INPUTS = {
  cash_on_hand:          1800000,
  monthly_burn:          120000,
  current_mrr:           40000,
  fundraising_timeline:  9,
  fundraise_confidence:  3,
  investor_traction:     3,
  monthly_retention:     0.99,
  monthly_growth_rate:   0.10,
  largest_customer_pct:  0.25,
  key_person_dependency: 3,
  hiring_difficulty:     3,
  technical_complexity:  3,
  customer_validation:   4,
}
