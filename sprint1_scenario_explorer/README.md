# Sprint 1 — Aviation Scenario Explorer

Techno-economic scenario tool for aviation and sustainable aviation fuel (SAF). Translates user-defined assumptions into CO₂ intensity, policy compliance gaps, and cost-per-seat outputs — benchmarked against IATA, ICAO, and ReFuelEU roadmap data.

**Stack:** FastAPI · React

---

## What it does

The tool takes five user inputs — aircraft concept, target year, SAF share, SAF pathway, and technology efficiency scenario — and returns:

- **CO₂ intensity** (gCO₂/RPK), benchmarked against moderate and ambitious IATA/ICAO trajectories
- **Policy compliance gap** vs. ReFuelEU mandate (2030: 6%, 2035: 20%, 2050: 70%)
- **Incremental SAF cost per seat** (USD), derived from pathway-specific price projections
- **SAF breakeven carbon price** ($/tCO₂)
- **Technology readiness proxy** (TRL 1–9, horizon-adjusted)

Every coefficient traces to a published source: [IATA-CR], [CAEP12], [CORSIA], [REFUELEU], [ICAO-LTAG], [ATAG-WP].

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

Full methodology, source citations, and worked examples: [`MODEL.md`](./MODEL.md)

---

*Not a certified engineering or financial model. For structured decision support and early-stage exploration.*
