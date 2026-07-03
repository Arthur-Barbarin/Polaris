"""Polaris Sprint 8 — Flight-Test Validation Harness dashboard.

Run:
    streamlit run dashboard/app.py

Tabs:
  Flight Track   ground track + cross-track / altitude / airspeed traces
  Test Cards     pass/fail card table for the selected scenario
  Campaign       pass matrix across all scenarios x seeds
  Triage         PCA scatter of runs coloured by predicted anomaly mode

All telemetry is synthetic simulator output (no real flight hardware).
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import json

import numpy as np
import pandas as pd
import streamlit as st

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from polaris_ft import (  # noqa: E402
    ALL_SCENARIOS, CARD_VERSION, FlightTriage, compute_metrics, default_mission,
    grade, simulate,
)
from polaris_ft.testcards import FlightMetrics  # noqa: E402

DATA = REPO / "data"


def _metrics_from_row(row: dict) -> FlightMetrics:
    fields = FlightMetrics.__dataclass_fields__.keys()
    return FlightMetrics(**{k: row[k] for k in fields})


@st.cache_data(show_spinner=False)
def load_campaign():
    """Precomputed campaign metrics (committed) — keeps the cloud app fast."""
    f = DATA / "campaign.json"
    if not f.is_file():
        return None
    runs = json.loads(f.read_text())["runs"]
    return [_metrics_from_row(r) for r in runs], runs

st.set_page_config(page_title="Polaris Flight-Test Harness", layout="wide")
st.title("Polaris Flight-Test Validation Harness")
st.caption(
    f"Closed-loop fixed-wing sim · navigation EKF in the loop · "
    f"versioned test cards (v{CARD_VERSION}) · PCA+GMM anomaly triage · "
    f"synthetic telemetry only"
)

tab_flt, tab_cards, tab_camp, tab_tri = st.tabs(
    ["Flight Track", "Test Cards", "Campaign", "Triage"]
)


@st.cache_data(show_spinner=False)
def run(scenario_name: str, seed: int, dt: float, backend: str):
    log = simulate(ALL_SCENARIOS[scenario_name](), seed=seed, dt=dt, backend=backend)
    return log, compute_metrics(log)


try:
    from polaris_ft.native import native_available
    _native = native_available()
except Exception:
    _native = False

with st.sidebar:
    st.header("Run")
    scen = st.selectbox("Scenario", list(ALL_SCENARIOS), index=0)
    seed = st.slider("Seed", 0, 15, 0)
    dt = st.select_slider("Timestep (s)", options=[0.1, 0.05, 0.02], value=0.05)
    backend = "python"
    if _native:
        backend = st.radio("Inner-loop backend", ["python", "native"], index=0,
                           help="native runs the RK4 dynamics + autopilot in C++")
    else:
        st.caption("C++ backend not built — running pure Python. "
                   "`cd cpp && make` to enable.")

log, metrics = run(scen, seed, dt, backend)
report = grade(metrics)


# ------------------------------------------------------------------- Flight tab
with tab_flt:
    mission = default_mission()
    wp_n = [w.n for w in mission.waypoints]
    wp_e = [w.e for w in mission.waypoints]

    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Ground track (N-E)")
        track = pd.DataFrame({"north": log.pn, "east": log.pe})
        # Chart: flown track + planned waypoints.
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(log.pe, log.pn, lw=1.2, label="flown")
        ax.plot(wp_e, wp_n, "o--", color="k", ms=6, label="planned")
        f = mission.geofence
        ax.plot([f.e_min, f.e_max, f.e_max, f.e_min, f.e_min],
                [f.n_min, f.n_min, f.n_max, f.n_max, f.n_min],
                ":", color="crimson", lw=1, label="geofence")
        ax.set_xlabel("East [m]"); ax.set_ylabel("North [m]")
        ax.legend(); ax.set_aspect("equal", "box")
        st.pyplot(fig)
    with c2:
        st.subheader("Verdict")
        st.metric("Result", "PASS" if report.passed else "FAIL")
        st.metric("Mission complete", str(metrics.mission_complete))
        st.metric("Cross-track RMS [m]", f"{metrics.cross_track_rms:.2f}")
        st.metric("Nav position RMSE [m]", f"{metrics.est_pos_rmse:.2f}")

    st.subheader("Time histories")
    df = pd.DataFrame({
        "t": log.t,
        "cross-track [m]": log.e_xt,
        "altitude [m]": log.h,
        "alt cmd [m]": log.h_cmd,
        "airspeed [m/s]": log.Va,
        "throttle": log.throttle,
    }).set_index("t")
    st.line_chart(df[["cross-track [m]"]])
    cc1, cc2 = st.columns(2)
    cc1.line_chart(df[["altitude [m]", "alt cmd [m]"]])
    cc2.line_chart(df[["airspeed [m/s]"]])


# --------------------------------------------------------------------- Cards tab
with tab_cards:
    st.subheader(f"Test card — {scen} (seed {seed})   ·   card v{report.version}")
    rows = []
    for c in report.results:
        rows.append({
            "Criterion": c.name,
            "Value": round(c.value, 3),
            "Bound": c.bound,
            "Unit": c.unit,
            "Required": c.required,
            "Result": "PASS" if c.passed else "FAIL",
        })
    cards_df = pd.DataFrame(rows)

    def _hl(v):
        return "background-color:#123d1f" if v == "PASS" else "background-color:#4d1414"
    st.dataframe(cards_df.style.map(_hl, subset=["Result"]),
                 use_container_width=True, hide_index=True)
    st.info("Tracking-error cards are evaluated on straight legs only "
            "(turn-transition and launch windows excluded), per flight-test practice.")


# ------------------------------------------------------------------ Campaign tab
@st.cache_data(show_spinner=True)
def campaign_live(seeds: int, dt: float):
    mets, rows = [], []
    for name, fn in ALL_SCENARIOS.items():
        for s in range(seeds):
            m = compute_metrics(simulate(fn(), seed=s, dt=dt))
            mets.append(m)
            rows.append({"scenario": name, "seed": s,
                         "passed": grade(m).passed, **m.as_dict()})
    return mets, pd.DataFrame(rows)


with tab_camp:
    precomputed = load_campaign()
    if precomputed is not None and not st.toggle("Recompute live", value=False):
        mets, runs = precomputed
        camp_df = pd.DataFrame([{"scenario": m.scenario,
                                 "passed": grade(m).passed, **m.as_dict()}
                                for m in mets])
        st.caption("Showing the committed campaign (data/campaign.json). "
                   "Toggle to recompute live.")
    else:
        seeds = st.slider("Seeds per scenario", 3, 12, 6)
        mets, camp_df = campaign_live(seeds, dt)
    st.subheader("Pass rate by scenario")
    summary = (camp_df.groupby("scenario")
               .agg(pass_rate=("passed", "mean"),
                    xt_rms=("cross_track_rms", "mean"),
                    xt_max=("cross_track_max", "mean"),
                    nav_rmse=("est_pos_rmse", "mean"))
               .reset_index())
    summary["pass_rate"] = (summary["pass_rate"] * 100).round(0).astype(int).astype(str) + "%"
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.bar_chart(camp_df.groupby("scenario")["passed"].mean())


# -------------------------------------------------------------------- Triage tab
with tab_tri:
    st.subheader("Anomaly triage — PCA(2) projection, coloured by predicted mode")
    n_clusters = max(8, len(ALL_SCENARIOS) + 3)
    tri = FlightTriage(n_components=4, n_clusters=n_clusters).fit(mets)
    preds = tri.predict(mets)
    Z = tri.transform_2d(mets)
    scatter = pd.DataFrame({
        "PC1": Z[:, 0], "PC2": Z[:, 1],
        "true": [p.label for p in preds],
        "predicted": [p.predicted_mode for p in preds],
    })
    acc = FlightTriage.accuracy(preds)
    st.metric("In-sample triage accuracy", f"{acc:.0%}")
    try:
        import altair as alt
        chart = (alt.Chart(scatter).mark_circle(size=90, opacity=0.8)
                 .encode(x="PC1", y="PC2", color="predicted",
                         tooltip=["true", "predicted"]))
        st.altair_chart(chart, use_container_width=True)
    except Exception:
        st.scatter_chart(scatter, x="PC1", y="PC2", color="predicted")
    st.caption("Fault families here are well separated by construction; accuracy "
               "reflects in-sample separability of synthetic scenarios, not a "
               "generalization claim on real flight data.")
