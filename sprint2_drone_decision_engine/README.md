# Sprint 2 — Drone Deployment Decision Engine

Go/No-Go deployment tool for commercial drone operations. Evaluates inspection, delivery, and agriculture scenarios against FAA regulatory constraints, platform physics, and benchmark operating costs — returning a single binding constraint label and a traceable resolution path.

**Stack:** FastAPI · React

---

## What it does

The user defines a deployment scenario (use case, platform tier, mission range, BVLOS status, annual volume) and the tool returns:

- **Verdict:** GO / CONDITIONAL / NO-GO
- **Binding constraint:** the single highest-priority blocking factor (payload, range, regulatory, economic, or scale)
- **Resolution path:** what specifically needs to change to flip the verdict
- **Economic metrics:** drone DOC per mission, human alternative cost, annual savings, break-even volume, platform payback months
- **Sensitivity sweeps:** labor cost ±30%, mission volume ±50%, BVLOS unlock value

The tool covers three use cases — infrastructure inspection, last-mile delivery, and agricultural spraying — across three platform tiers (Light / Professional / Heavy) and the current FAA Part 107 / Part 108 regulatory framework.

Every cost coefficient traces to a published source: [FAA-107], [FAA-108], [MU-EXT], [PwC-2016], [BARCLAYS-2026], [MANNA-2025].

---

## Constraint priority order

1. Payload (hardware — cannot be waived)
2. Range / endurance (physics — cannot be waived)
3. Regulatory / BVLOS (legal — resolves via Part 107 waiver or Part 108 permit, expected 2026–27)
4. Economic (drone costs exceed human alternative)
5. Scale / utilization (insufficient volume — resolves via DaaS or volume growth)
6. Urban airspace (conditional — resolves via LAANC authorization)

---

## How to run

**Backend**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

---

## Model reference

Full methodology, FAA regulatory constants, platform tiers, economic coefficients, and worked examples: [`MODEL.md`](./MODEL.md)

---

*Not a certified engineering or financial model. For structured decision support and early-stage exploration.*
