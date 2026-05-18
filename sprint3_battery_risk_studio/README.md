# Sprint 3 — Fleet Energy & Battery Risk Studio

ML-powered battery prognostics platform built on the NASA PCoE lithium-ion dataset. Predicts State of Health (SOH) and Remaining Useful Life (RUL) with SHAP explainability, physics-informed route energy simulation, and unsupervised operating regime clustering.

**Stack:** Python · Streamlit · scikit-learn · SHAP  
🔗 **[Live demo →](https://arthur-barbarin-polaris.streamlit.app)**

---

## What it does

Three tabs, each a self-contained analytical layer:

**Tab 1 — Route Energy Risk**  
Physics-informed mission simulation (momentum theory, Glauert forward-flight inflow, ISA atmosphere). Given vehicle parameters and a route, computes energy budget by flight phase and returns a GO/NO-GO verdict with margin against battery SOH.

**Tab 2 — Battery Risk**  
Per-cycle SOH and RUL predictions via trained Random Forest models, with a SHAP waterfall plot explaining each prediction. Covers 4 NASA PCoE cells (B0005–B0018); B0018 is held out as the test cell.

**Tab 3 — Operating Regime Explorer**  
PCA + GMM unsupervised clustering over 8 cycle features. Automatically selects the number of regimes via BIC, renders a degradation trajectory in PCA space, and surfaces coverage gaps across the test fleet.

---

## Safety thresholds

| Threshold | Value | Meaning |
|---|---|---|
| Warning | 80% SOH | Flag for inspection |
| End of life | 70% SOH | Ground the vehicle (NASA convention) |

---

## How to run

```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

The app expects trained model artifacts in `outputs/model_artifacts/`. Run `notebooks/04_model_training.ipynb` first if they are missing.

---

## Project structure

```
sprint3_battery_risk_studio/
├── app/
│   └── streamlit_app.py       # 3-tab Streamlit dashboard
├── src/
│   ├── battery_features.py    # NASA .mat loading + feature extraction
│   ├── models.py              # Random Forest training (SOH + RUL)
│   ├── evaluation.py          # Model evaluation metrics
│   ├── explainability.py      # SHAP computation
│   ├── route_simulation.py    # Physics-based energy simulation
│   └── regime_analysis.py     # PCA + GMM clustering
├── data/
│   ├── raw/                   # NASA PCoE .mat files (B0005–B0018)
│   └── processed/             # Extracted feature CSV
├── notebooks/
│   ├── 02_battery_feature_extraction.ipynb
│   └── 04_model_training.ipynb
├── outputs/
│   ├── figures/               # Diagnostic plots
│   └── model_artifacts/       # Trained .pkl models + feature metadata
└── requirements.txt
```

---

*NASA dataset: Saha, B. and Goebel, K. (2007). Battery Data Set, NASA Ames Prognostics Data Repository.*  
*Not for operational use. Research preview.*
