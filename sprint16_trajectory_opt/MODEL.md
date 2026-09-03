# MODEL.md — Trajectory Optimization Studio: formulation, solver, and choices

This document explains *what* is optimized and *why* it is posed the way it is.
The through-line: an optimizer is only trustworthy if you can see the whole
chain — from the physics, to the convex program, to the solver, to a
closed-form check. Every link here is exposed and tested.

## 1. Vehicle model and condensing (`dynamics.py`)

The vehicle is a 2-D point mass, horizontal `x` and vertical `h`, with
acceleration as the control. Each axis is a double integrator, exactly
discretized over a step `dt`:

```
x_{k+1} = x_k + vx_k·dt + ½ ax_k·dt²      vx_{k+1} = vx_k + ax_k·dt
```

For optimization the dynamics are **condensed**: every future state is written
as an affine function of the stacked control sequence,

```
X = Φ·x₀ + Γ·U
```

with `Φ` (4N×4) and `Γ` (4N×2N, lower block-triangular). This is the standard
MPC condensing step. It turns every state constraint into a linear inequality
in `U`, so the whole problem is a QP in the controls alone — and it is checked
against a direct integration rollout to 1e-10 in the tests.

## 2. The optimization problem (`problem.py`)

```
minimize   Σ_k dt·(w_x·ax_k² + w_h·ah_k²)          control energy
subject to s_N = goal                              arrive at rest at the target
           |ax| ≤ ax_max,  |ah| ≤ ah_max           thrust / comfort envelope
           |vx| ≤ vx_max,  |vh| ≤ vh_max           speed envelope
           h_k ≥ h_floor                           terrain / safety floor
           h_k ≥ h_noise   for k in the corridor   noise-abatement segment
```

Control energy `∫u² dt` is the classic minimum-effort objective and a clean
proxy for battery draw and passenger comfort. Everything maps to the QP data:
the objective is `½UᵀPU` with `P` diagonal in the axis weights, the goal is a
set of equality rows (`l = u`), and every envelope/floor/corridor limit is a
pair of linear bounds on `Γ·U` (the state) or on `U` (the control).

**Why the corridor is a time window.** The noise-sensitive area is a stretch of
ground. For a monotone A→B repositioning, time index maps to along-track
distance, so "stay above `h_noise` while over the town" becomes "stay above
`h_noise` for `k ∈ [k₀, k₁]`" — a set of linear bounds. Tying it to horizontal
*position* instead would couple the constraint to the decision variables
non-linearly; the time-window form keeps the problem an honest QP.

## 3. The solver (`qp.py`)

The QP is solved by **ADMM, the OSQP algorithm**, implemented from scratch:

```
minimize ½zᵀPz + qᵀz   s.t.  l ≤ Az ≤ u
```

Each iteration solves one linear system with a *fixed* KKT matrix
`[[P+σI, Aᵀ],[A, −ρ⁻¹I]]` (inverted once and reused) and projects onto the box
`[l, u]`. Two details make a fixed-parameter ADMM actually converge across
differently-scaled problems, and both are implemented:

- **Scaled stopping tolerances** — the primal and dual residuals are compared to
  `ε_abs + ε_rel·(scale)` using the problem's own magnitudes, not a bare
  constant.
- **Adaptive ρ** — every 100 iterations `ρ` is rebalanced by
  `ρ·√(primal/dual)` and the KKT matrix refactored, so the primal and dual
  residuals drive down together.

The tests pin the solver to analytic QP solutions — box projection, the
equality-constrained minimum `1/n`, saturation on both bounds, and a random SPD
equality-constrained QP matched to its closed-form KKT solution to 1e-6.

## 4. Verification against the closed form (`problem.py`, `metrics.py`)

Two independent checks keep the optimizer honest:

- **Solver vs analytic QP.** Above — machine-precision agreement on problems
  with known solutions.
- **Optimum vs optimal-control law.** For a double integrator the minimum-energy
  control is linear in time and the position is a cubic; the boundary conditions
  fix the coefficients. With the path constraints relaxed, the discrete QP
  optimum reproduces that analytic trajectory to **0.004 m RMS**, and the
  control energy hits the exact `12 D²/T³` — a **25%** saving over the bang-bang
  `16 D²/T³`. When two derivations that share no code agree to discretization
  error, both are almost certainly right.

## 5. The metrics that matter (`metrics.py`)

- **Energy and saving vs bang-bang** — the headline efficiency number.
- **Constraint margins** — min floor clearance, min corridor clearance, peak
  acceleration, terminal error; all must be non-negative / near-zero for the
  solution to count as feasible.
- **Price of the noise corridor** — `E(with corridor) − E(without)`, the energy
  cost of the community-noise constraint, and the sweep showing it rise
  monotonically as the floor tightens.

This mirrors the earlier sprints' pattern — take the same scenario, optimize it
under the real constraint and without it, and report the difference — but here
the safeguard is a *design constraint* and the "risk ratio" analogue is the
energy price of respecting it.

## 6. What this is not

- Not a full flight dynamics or trajectory-tracking model — it decides the
  reference *shape*; an inner loop would fly it.
- Not a non-convex planner — no obstacle-avoidance around peaks, no minimum-time
  or free-final-time problems (those break convexity or need SQP/NLP).
- Not multi-vehicle — one point mass, one trajectory.

Each is a clean extension of the same three pieces — a richer model in
`dynamics.py`, more rows in `problem.py`, an SQP wrapper around `qp.py` — without
disturbing the convex core, which is the part that has to stay verifiable.

*Engineering clarity for complex futures.*
