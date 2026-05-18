# Polaris

Decision-support tools for aerospace and advanced transport systems — built to translate engineering assumptions into structured, benchmark-referenced outputs.

Each sprint is a self-contained tool targeting a different domain and stack. All models use sourced physical constants and published industry references; no synthetic scores.

---

## Sprints

### [Sprint 1 — Aviation Scenario Explorer](./sprint1_scenario_explorer/)
**Stack:** FastAPI · React  
Techno-economic scenario tool for aviation and SAF. Translates user-defined assumptions (SAF share, technology efficiency, target year) into CO₂ intensity, policy compliance gaps, and cost-per-seat outputs, benchmarked against IATA, ICAO, and ReFuelEU roadmap data.

### [Sprint 2 — Drone Deployment Decision Engine](./sprint2_drone_decision_engine/)
**Stack:** FastAPI · React  
Go/No-Go deployment tool for commercial drone operations. Evaluates inspection, delivery, and agriculture scenarios against FAA regulatory constraints, platform physics, and benchmark operating costs — returning a single binding constraint label and a traceable resolution path.

### [Sprint 3 — Fleet Energy & Battery Risk Studio](./sprint3_battery_risk_studio/)
**Stack:** Python · Streamlit · scikit-learn · SHAP  
ML-powered battery prognostics platform built on the NASA PCoE lithium-ion dataset. Predicts State of Health and Remaining Useful Life via Random Forest models with SHAP explainability, physics-informed route energy simulation, and unsupervised operating regime clustering (PCA + GMM).  
🔗 **[Live demo →](https://arthur-barbarin-polaris.streamlit.app)**

---

*Engineering clarity for complex futures.*
