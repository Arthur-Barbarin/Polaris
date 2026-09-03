# Sprint 16 — Trajectory Optimization Studio

**Stack:** Python · NumPy · pytest

A **minimum-energy trajectory optimizer** for a point-mass eVTOL/UAV. It poses
the descent-and-reposition problem as one convex quadratic program — energy
objective, arrival constraint, acceleration/velocity envelope, altitude floor,
and a noise-abatement corridor — and solves it with an **in-house ADMM QP
solver** (no external optimization dependency). The optimizer is not a black
box: the solver is validated against analytic QP solutions, and the optimal
trajectory is validated against the closed-form minimum-energy control law.

> Answers: *"What is the least-energy way to fly this vehicle from A to rest at
> B while staying above the terrain, holding altitude over the noise-sensitive
> area, and inside the acceleration envelope — and how much does the noise
> constraint actually cost?"*

This is a new algorithmic domain for the portfolio — **numerical optimization
and optimal control** — rather than the estimation, simulation, and
safety-monitoring of the earlier sprints.

---

## The two things a visitor should try

1. **Solve the descent and read the numbers.**
   ```bash
   python scripts/run_opt.py solve
   ```
   A 300 m → 60 m descent over 900 m and 60 s, as a 240-variable QP. The
   optimizer arrives at the goal to **3e-7 m**, holds the **200 m** noise
   corridor exactly, clears the floor by 15 m, stays inside the accel envelope,
   and uses **25% less control energy** than a bang-bang baseline — while the
   unconstrained version matches the analytic optimum to **0.004 m RMS**.

2. **Sweep the noise floor and price the constraint.**
   ```bash
   python scripts/run_opt.py sweep
   ```
   Raising the required altitude over the community from 160 m to 260 m drives
   the optimal energy up **monotonically** (50.0 → 72.2). That curve is the
   quantified cost of flying higher over the town — the kind of trade a
   community-noise vs operating-cost decision actually needs.

---

## What's modelled (and the honesty notes)

**The optimizer is a QP, and the QP solver is hand-rolled and verified.** The
trajectory problem is condensed to a quadratic program in the control sequence
and solved by an ADMM iteration (the OSQP algorithm) implemented in
`traj/qp.py`: one KKT factorization, a linear solve and a box projection per
iteration, adaptive `ρ`, and scaled stopping tolerances. The tests pin it to
analytic QP solutions (box projection, equality-constrained minimum, a random
SPD problem) to machine precision.

**The optimum is checked against the closed form.** For a double integrator the
minimum-energy control is linear in time and the position is a cubic. With the
path constraints relaxed, the discrete QP optimum reproduces that analytic
trajectory to **0.004 m RMS** — pure discretization error — and recovers the
**exact 25%** energy penalty a minimum-time bang-bang profile pays
(`16 D²/T³` vs `12 D²/T³`).

**The constraints are kept convex, deliberately.** The altitude floor and the
time-windowed noise corridor are linear inequalities, so the problem stays a
QP with a global optimum. Clearing a *peaked* obstacle (flying over a mountain)
is a non-convex constraint and is out of scope by design — noted rather than
faked.

**The vehicle is a point mass.** Double integrator per axis, acceleration as the
control and its square as the energy proxy. No attitude, rotor, or aerodynamic
model. This is the level at which trajectory *shape* is decided; a higher-fidelity
inner loop would track the resulting reference.

**Fully deterministic** — no randomness anywhere; every number is reproducible.

---

## Architecture (one paragraph; full detail in `MODEL.md`)

Five small, independently testable layers. `qp.py` is the ADMM QP solver.
`dynamics.py` is the double-integrator model and the condensing step that writes
every future state as an affine function of the controls. `problem.py` assembles
the energy objective and the constraint rows (goal, envelope, floor, corridor)
into `(P, q, A, l, u)`, and provides the analytic optimum for verification.
`baselines.py` is the bang-bang foil. `metrics.py` solves and scores — energy,
constraint margins, saving vs baseline, and the price of the noise corridor.

```
traj/
  qp.py         # in-house ADMM (OSQP-style) convex QP solver
  dynamics.py   # double-integrator model + condensed prediction maps
  problem.py    # energy QP assembly + analytic minimum-energy optimum
  baselines.py  # bang-bang (minimum-time) reference
  metrics.py    # solve + score: energy, margins, savings, noise price
scripts/
  run_opt.py    # CLI: solve, or sweep the noise corridor
  report.py     # markdown run report
  verify.py     # reproduces every headline number below
tests/          # 20 tests: QP vs analytic, dynamics, problem, metrics
reports/        # sample run report
```

---

## Reproduce every number

```bash
python scripts/verify.py     # deterministic, no external solver, exits non-zero on drift
python -m pytest -q          # 20 tests
```

`verify.py` asserts each headline:

- **solver:** ADMM converges (primal 3e-7, dual 1e-6).
- **feasibility:** reaches the goal (3e-7 m), clears the floor (15 m), holds the
  noise corridor (0.000 m), respects the accel envelope (1.49 ≤ 3.0 m/s²).
- **benefit:** 24.99% energy saving vs bang-bang; the noise corridor adds
  positive energy (+7.66).
- **analytic match:** unconstrained QP equals the closed-form optimum
  (RMS 0.0045 m).
- **monotonicity:** optimal energy rises with the noise floor
  (50.0 → 52.4 → 55.9 → 60.3 → 65.8 → 72.2).

See `reports/run_report.md` for a full sample report.

---

*Engineering clarity for complex futures.*
