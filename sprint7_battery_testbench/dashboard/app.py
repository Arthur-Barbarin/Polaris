"""Polaris Battery Testbench - Streamlit dashboard.

Run:
  streamlit run dashboard/app.py

Four tabs:
  Live Bench       - drive the SCPI server interactively
  SOC Estimators   - compare coulomb counting vs EKF on a fresh run
  Cycling & SoH    - cycle-life curves from data/cycle_records.json
  Failure Triage   - PCA scatter + per-cycle predictions
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import streamlit as st

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from polaris_bms import Cell, CoulombCounter, Ekf, Fault
from polaris_bms.cycler import CycleRecord, run_cycling_campaign
from polaris_bms.signals import inject_current_noise, inject_voltage_noise
from polaris_bms.triage import FailureTriage, rul_projection, to_matrix


st.set_page_config(page_title="Polaris BMS Testbench", layout="wide")
st.title("Polaris BMS Testbench")
st.caption(
    "C++ 2nd-order Thévenin cell · pytest-driven virtual SCPI bench · "
    "EKF SOC estimation · PCA+GMM failure triage"
)


tab_live, tab_soc, tab_cyc, tab_tri = st.tabs(
    ["Live Bench", "SOC Estimators", "Cycling & SoH", "Failure Triage"]
)


# --------------------------------------------------------------------------- #
# Live bench
# --------------------------------------------------------------------------- #
with tab_live:
    st.subheader("Drive a single cell - constant-current profile")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        i_a = st.slider("Current (A, + = discharge)", -3.2, 5.0, 1.6, 0.1)
    with col2:
        dur_s = st.slider("Duration (s)", 60, 3600, 600, 60)
    with col3:
        T_c = st.slider("Temperature (°C)", -20, 60, 25, 5)
    with col4:
        fault_label = st.selectbox(
            "Injected fault",
            [f.name for f in Fault],
            index=0,
        )
        sev = st.slider("Severity", 0.0, 1.0, 0.0, 0.05)

    if st.button("Run live bench", type="primary"):
        cell = Cell(soc0=1.0, temperature_k=T_c + 273.15)
        cell.set_fault(Fault[fault_label], sev)
        rng = np.random.default_rng(0)
        rows = []
        for k in range(int(dur_s)):
            v = cell.step(i_a, 1.0)
            v_meas = inject_voltage_noise(v, rng, std_v=0.002)
            rows.append({
                "t_s": k,
                "V_term": v_meas,
                "I_A": i_a,
                "SOC": cell.snapshot().soc,
            })
        df = pd.DataFrame(rows)
        c1, c2 = st.columns(2)
        with c1:
            st.line_chart(df.set_index("t_s")[["V_term"]], height=260)
            st.caption("Terminal voltage (V)")
        with c2:
            st.line_chart(df.set_index("t_s")[["SOC"]], height=260)
            st.caption("State of charge (0..1)")
        st.dataframe(df.tail(8), use_container_width=True)


# --------------------------------------------------------------------------- #
# SOC estimator comparison
# --------------------------------------------------------------------------- #
with tab_soc:
    st.subheader("Coulomb counting vs Extended Kalman Filter")
    bias = st.slider("Current shunt bias (A)", 0.0, 0.2, 0.05, 0.01)
    guess_err = st.slider("Initial SOC guess error", -0.5, 0.5, 0.3, 0.05)
    if st.button("Run estimator comparison"):
        cell = Cell(soc0=1.0)
        ekf = Ekf(soc_guess=float(np.clip(1.0 - guess_err, 0.05, 0.95)),
                  covariance_soc=0.2)
        cc = CoulombCounter(capacity_ah=cell.snapshot().q_now_ah,
                            soc=float(np.clip(1.0 - guess_err, 0.05, 0.95)))
        rng = np.random.default_rng(11)
        n = 2 * 3600
        t = np.arange(n)
        prof = np.where((t // 600) % 4 == 0,  3.2,
               np.where((t // 600) % 4 == 1,  0.0,
               np.where((t // 600) % 4 == 2, -1.6, 0.0)))
        rows = []
        for k, i_true in enumerate(prof):
            v = cell.step(float(i_true), 1.0)
            v_meas = inject_voltage_noise(v, rng, std_v=0.002)
            i_meas = inject_current_noise(float(i_true), rng, std_a=0.01, bias_a=bias)
            ekf.step(i_meas, v_meas, 298.15, 1.0)
            cc.step(i_meas, 1.0)
            rows.append({"t_s": k, "SOC_true": cell.snapshot().soc,
                         "SOC_EKF": ekf.soc, "SOC_CC": cc.soc})
        df = pd.DataFrame(rows)
        st.line_chart(df.set_index("t_s"), height=320)
        err_cc = float(np.sqrt(np.mean((df.SOC_true - df.SOC_CC) ** 2)))
        err_ekf = float(np.sqrt(np.mean((df.SOC_true - df.SOC_EKF) ** 2)))
        c1, c2, c3 = st.columns(3)
        c1.metric("Coulomb counting RMS error", f"{err_cc:.4f}")
        c2.metric("EKF RMS error", f"{err_ekf:.4f}")
        c3.metric("EKF advantage", f"{100*(1-err_ekf/err_cc):+.1f}%")


# --------------------------------------------------------------------------- #
# Cycling & SoH
# --------------------------------------------------------------------------- #
with tab_cyc:
    st.subheader("Accelerated cycling - SoH and RUL projection")
    records_path = REPO / "data" / "cycle_records.json"
    if not records_path.exists():
        st.info("Run `python3 scripts/run_cycling_campaign.py` first to populate data/.")
    else:
        records = json.loads(records_path.read_text())
        df = pd.DataFrame(records)
        st.line_chart(df.pivot(index="cycle", columns="fault", values="soh_pct"),
                      height=320)
        st.caption("SoH per scenario (%)")
        rul_path = REPO / "data" / "rul_projections.json"
        if rul_path.exists():
            rul = json.loads(rul_path.read_text())
            st.subheader("Remaining Useful Life (cycles to 80% SoH)")
            st.dataframe(pd.DataFrame(
                {"scenario": list(rul.keys()), "cycles_to_eol": list(rul.values())}
            ), use_container_width=True)


# --------------------------------------------------------------------------- #
# Failure triage
# --------------------------------------------------------------------------- #
with tab_tri:
    st.subheader("PCA + Gaussian Mixture triage")
    records_path = REPO / "data" / "cycle_records.json"
    if not records_path.exists():
        st.info("Run `python3 scripts/run_cycling_campaign.py` first.")
    else:
        raw = json.loads(records_path.read_text())
        recs = [CycleRecord(**r) for r in raw]
        training = [r for r in recs if r.cycle > 1]
        triage = FailureTriage(n_components=4, n_clusters=8).fit(training)
        preds = triage.predict(training)
        X, y = to_matrix(training)
        Xp = triage.pca.transform(triage.scaler.transform(X))
        df_scatter = pd.DataFrame({"PC1": Xp[:, 0], "PC2": Xp[:, 1],
                                   "true": y,
                                   "pred": [p.predicted_mode for p in preds]})
        st.scatter_chart(df_scatter, x="PC1", y="PC2", color="true", height=380)
        st.caption("Cycle features projected onto the first two principal components, "
                   "coloured by true fault label.")
        acc = sum(p.predicted_mode == r.fault for p, r in zip(preds, training)) / len(training)
        st.metric("In-sample triage accuracy", f"{100*acc:.1f}%")
        st.dataframe(
            df_scatter.groupby(["true", "pred"]).size().unstack(fill_value=0),
            use_container_width=True,
        )
