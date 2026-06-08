# Sprint 4 — Founder Failure Mode Analyzer

Aerospace-grade fault tree analysis applied to startup survival.

**Stack:** React · D3 · Vite (pure frontend, no backend)

---

## What it does

Most startup tools answer: *"What will happen?"*  
This tool answers: *"How will this fail?"*

The tool imports two methodologies from aerospace reliability engineering — FMEA (MIL-STD-1629A) and fault tree analysis (IEC 61025) — and applies them to the problem of startup survival. It maps 11 inputs across 4 risk branches to a live fault tree, identifies the primary failure mechanism, and runs Monte Carlo uncertainty propagation across 10,000 simulations.

---

## The model

**Top event:** Fail to reach next financing milestone before runway exhaustion.

**4 branches (OR gates):**
- **Capital** — Runway Exhaustion · Fundraise Delayed · Cost Shock  
- **Revenue** — Poor Retention · Growth Stall · Customer Concentration  
- **Team** — Key Person Risk · Hiring Bottleneck  
- **Product** — Technical Risk · Market Misfit

Each leaf node has a calibrated transfer function mapping inputs to failure probabilities, anchored against Series A benchmarks (SaaStr, Crunchbase base rates, empirical Series A thresholds).

Monte Carlo samples each input from a distribution (σ = 10–20% of mean), propagates through the fault tree deterministically, and reports expected failure probabilities under input uncertainty. Retention and growth rate are correlated in sampling (ρ = 0.55) via Cholesky decomposition.

**Outputs:**
1. Live fault tree with probability propagation
2. Resilience Index (weighted branch failure average)
3. Risk decomposition by branch
4. Binding constraint — single highest-risk failure mode
5. Sensitivity ranking — which assumption changes the picture most
6. Mitigation card with highest-leverage action

---

## Tagline

> What if startups were analyzed the same way aerospace engineers analyze aircraft failures?

---

## Polaris context

Sprint 4 of the [Polaris Decision Modeling Studio](https://github.com/your-username/polaris).  
Previous sprints: Scenario Explorer · Drone Decision Engine · Battery Risk Studio
