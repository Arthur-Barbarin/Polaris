"""Polaris Sprint 9 — Precision-Landing Validation Studio dashboard.

Run:  streamlit run dashboard/app.py

Tabs:
  Approach     descent trajectory, ground track vs pad, phase + vision timeline
  Test Cards   landing acceptance pass/fail for the selected approach
  Dispersion   Monte-Carlo touchdown scatter + CEP ellipse
  Triage       PCA scatter of approaches coloured by predicted mode
  Campaign     PASS / FAIL / REJECT matrix + CEP per scenario

All camera / GPS / telemetry are synthetic measurements (projected geometry),
not real image pixels or flight hardware.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from polaris_pl import (  # noqa: E402
    ALL_SCENARIOS, CARD_VERSION, LandingTriage, cep, compute_metrics, grade, simulate,
)
from polaris_pl.testcards import LandingMetrics  # noqa: E402

DATA = REPO / "data"

st.set_page_config(page_title="Polaris Precision-Landing Studio", layout="wide")
st.title("Polaris Precision-Landing Validation Studio")
st.caption(f"Vision-guided multirotor descent · GPS→vision fusion · landing test "
           f"cards (v{CARD_VERSION}) · CEP dispersion · PCA+GMM triage · "
           f"synthetic measurements only")


@st.cache_data(show_spinner=False)
def run(scen: str, seed: int, dt: float):
    log = simulate(ALL_SCENARIOS[scen](), seed=seed, dt=dt)
    return log, compute_metrics(log)


@st.cache_data(show_spinner=True)
def dispersion(scen: str, n: int, dt: float):
    pts, outs = [], defaultdict(int)
    for s in range(n):
        log = simulate(ALL_SCENARIOS[scen](), seed=s, dt=dt)
        outs[log.outcome] += 1
        if log.outcome == "LANDED":
            pts.append([log.touchdown_x, log.touchdown_y])
    return np.array(pts) if pts else np.empty((0, 2)), dict(outs)


@st.cache_data(show_spinner=False)
def load_metrics():
    f = DATA / "campaign.json"
    if not f.is_file():
        return None
    runs = json.loads(f.read_text())["runs"]
    flds = LandingMetrics.__dataclass_fields__.keys()
    return [LandingMetrics(**{k: r[k] for k in flds}) for r in runs]


with st.sidebar:
    st.header("Approach")
    scen = st.selectbox("Scenario", list(ALL_SCENARIOS), index=0)
    seed = st.slider("Seed", 0, 30, 0)
    dt = st.select_slider("Timestep (s)", [0.05, 0.02, 0.01], value=0.02)

log, metrics = run(scen, seed, dt)
report = grade(metrics)

tabs = st.tabs(["Approach", "Test Cards", "Dispersion", "Triage", "Campaign"])

# --------------------------------------------------------------- Approach tab
with tabs[0]:
    import matplotlib.pyplot as plt
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Ground track & descent")
        fig, (axg, axh) = plt.subplots(1, 2, figsize=(9, 4))
        axg.plot(log.x, log.y, lw=1.2, label="flown")
        axg.scatter([log.pad_xy[0]], [log.pad_xy[1]], c="crimson", marker="x",
                    s=90, label="pad (actual)")
        axg.scatter([0], [0], c="gray", marker="+", s=90, label="pad (surveyed)")
        axg.set_xlabel("East [m]"); axg.set_ylabel("North [m]")
        axg.set_aspect("equal", "box"); axg.legend(fontsize=7)
        axh.plot(log.t, log.z, lw=1.4)
        axh.set_xlabel("t [s]"); axh.set_ylabel("altitude [m]")
        st.pyplot(fig)
    with c2:
        st.subheader("Verdict")
        st.metric("Outcome", report.outcome)
        if metrics.landed:
            st.metric("Touchdown error [m]", f"{metrics.touchdown_lateral:.3f}")
            st.metric("Touchdown sink [m/s]", f"{metrics.touchdown_sink:.2f}")
        if report.outcome == "REJECT":
            st.metric("Go-around reason", log.go_around_reason)
        st.metric("Vision on final [%]", f"{100*metrics.vision_avail_final:.0f}")
    st.subheader("Vision availability & lateral error")
    df = pd.DataFrame({"t": log.t, "altitude [m]": log.z,
                       "lateral error (true) [m]": log.lateral_true,
                       "vision valid": log.vision_valid.astype(int)}).set_index("t")
    st.line_chart(df[["lateral error (true) [m]", "vision valid"]])

# -------------------------------------------------------------- Test Cards tab
with tabs[1]:
    st.subheader(f"Landing test card — {scen} (seed {seed}) · v{report.version}")
    st.write(f"**Outcome: {report.outcome}**"
             + ("" if report.outcome in ("PASS", "FAIL")
                else "  — go-arounds (REJECT) are a safe abort, not a card failure."))
    if report.results:
        rows = [{"Criterion": c.name, "Value": round(c.value, 3), "Bound": c.bound,
                 "Unit": c.unit, "Result": "PASS" if c.passed else "FAIL"}
                for c in report.results]
        df = pd.DataFrame(rows)
        st.dataframe(df.style.map(
            lambda v: "background-color:#123d1f" if v == "PASS" else "background-color:#4d1414",
            subset=["Result"]), use_container_width=True, hide_index=True)

# -------------------------------------------------------------- Dispersion tab
with tabs[2]:
    n = st.slider("Approaches", 10, 60, 30)
    pts, outs = dispersion(scen, n, dt)
    st.write("Outcomes:", outs)
    if len(pts) >= 2:
        c = cep(pts)
        import matplotlib.pyplot as plt
        from matplotlib.patches import Circle, Ellipse
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.scatter(pts[:, 0], pts[:, 1], s=18, alpha=0.7)
        ax.scatter([0], [0], c="crimson", marker="x", s=90, label="pad")
        ax.add_patch(Circle((c.mean_x, c.mean_y), c.cep50, fill=False,
                            color="tab:green", label=f"CEP50={c.cep50:.3f} m"))
        ax.add_patch(Circle((c.mean_x, c.mean_y), c.cep95, fill=False,
                            color="tab:orange", ls="--", label=f"CEP95={c.cep95:.3f} m"))
        ax.add_patch(Ellipse((c.mean_x, c.mean_y), 2*c.ellipse_a, 2*c.ellipse_b,
                             angle=np.degrees(c.ellipse_angle), fill=False,
                             color="gray", ls=":"))
        ax.set_aspect("equal", "box"); ax.set_xlabel("East [m]"); ax.set_ylabel("North [m]")
        ax.legend(fontsize=7)
        st.pyplot(fig)
        m1, m2, m3 = st.columns(3)
        m1.metric("CEP50 precision [m]", f"{c.cep50:.3f}",
                  help="about the sample mean (scatter)")
        m2.metric("Mean bias [m]", f"{c.bias:.3f}",
                  help="systematic touchdown offset from the pad")
        m3.metric("CEP50 accuracy [m]", f"{c.cep50_pad:.3f}",
                  help="about the pad (bias + scatter) — the honest landing error")
    else:
        st.info("This scenario produced no landings (all go-arounds / rejects).")

# ------------------------------------------------------------------ Triage tab
with tabs[3]:
    mets = load_metrics()
    if mets is None:
        st.info("Run `python scripts/run_campaign.py` to generate data/campaign.json.")
    else:
        tri = LandingTriage(n_components=6, n_clusters=16).fit(mets)
        preds = tri.predict(mets)
        Z = tri.transform_2d(mets)
        acc = LandingTriage.accuracy(preds)
        st.metric("In-sample triage accuracy", f"{acc:.0%}")
        sc = pd.DataFrame({"PC1": Z[:, 0], "PC2": Z[:, 1],
                           "true": [p.label for p in preds],
                           "predicted": [p.predicted_mode for p in preds]})
        try:
            import altair as alt
            st.altair_chart(alt.Chart(sc).mark_circle(size=80, opacity=0.8).encode(
                x="PC1", y="PC2", color="predicted", tooltip=["true", "predicted"]),
                use_container_width=True)
        except Exception:
            st.scatter_chart(sc, x="PC1", y="PC2", color="predicted")
        st.caption("NOMINAL / CROSSWIND / OFFSET_PAD / GPS_BIAS overlap: a "
                   "successful GPS→vision handover makes a compensated fault look "
                   "near-nominal in the telemetry. The GPS-vision disagreement "
                   "feature is what still separates the pad-offset / GPS-bias cases.")

# ---------------------------------------------------------------- Campaign tab
with tabs[4]:
    f = DATA / "campaign.json"
    if not f.is_file():
        st.info("Run `python scripts/run_campaign.py` first.")
    else:
        blob = json.loads(f.read_text())
        runs = pd.DataFrame(blob["runs"])
        mat = (runs.groupby(["scenario", "outcome"]).size()
               .unstack(fill_value=0))
        for col in ["PASS", "FAIL", "REJECT", "TIMEOUT"]:
            if col not in mat: mat[col] = 0
        st.subheader("Outcome matrix")
        st.dataframe(mat[["PASS", "FAIL", "REJECT", "TIMEOUT"]],
                     use_container_width=True)
        if blob.get("cep"):
            st.subheader("Touchdown CEP by scenario (precision vs accuracy)")
            cep_df = pd.DataFrame(blob["cep"]).T[["n", "cep50", "bias", "cep50_pad"]]
            cep_df.columns = ["n", "CEP50 (precision)", "bias", "CEP50 (accuracy)"]
            st.dataframe(cep_df, use_container_width=True)
