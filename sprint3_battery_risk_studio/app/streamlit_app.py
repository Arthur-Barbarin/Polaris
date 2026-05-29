"""
Polaris Fleet Energy & Battery Risk Studio
===========================================
Streamlit dashboard — 3 tabs

  Tab 1 — Route Energy Risk     ← physics-informed energy simulation
  Tab 2 — Battery Risk          ← live ML predictions + SHAP
  Tab 3 — Operating Regime      ← PCA + GMM unsupervised clustering

Run locally:
    streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Path setup — makes `src/` importable when running from repo root ──────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import joblib
import json
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import shap
import streamlit as st

from battery_features import SOH_WARNING_THRESHOLD, SOH_EOL_THRESHOLD
from explainability import compute_shap, top_drivers
from route_simulation import (
    VehicleParams, MissionParams, FlightResult,
    simulate_mission, power_curve, CELL_ENERGY_WH,
)
from regime_analysis import (
    fit_regimes, regime_summary, DEFAULT_FEATURES, FEATURE_LABELS,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Polaris Battery Risk Studio",
    page_icon="⚡",
    layout="wide",
)

# ── Paths ─────────────────────────────────────────────────────────────────────
ARTIFACTS = ROOT / "outputs" / "model_artifacts"
DATA_PATH  = ROOT / "data" / "processed" / "battery_features.csv"

# ── Colour tokens ─────────────────────────────────────────────────────────────
GREEN   = "#2ECC71"
YELLOW  = "#F39C12"
RED     = "#E74C3C"
BLUE    = "#2980B9"
ORANGE  = "#E67E22"

# ── Plotly layout defaults (dark theme) ───────────────────────────────────────
_PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(26,29,46,0.6)",
    font=dict(color="#FAFAFA", size=12),
    margin=dict(l=50, r=20, t=40, b=50),
    legend=dict(
        bgcolor="rgba(0,0,0,0.3)",
        bordercolor="rgba(255,255,255,0.1)",
        borderwidth=1,
    ),
    xaxis=dict(gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.1)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.1)"),
)


def _apply_layout(fig: go.Figure, **kwargs) -> go.Figure:
    layout = {**_PLOTLY_LAYOUT, **kwargs}
    fig.update_layout(**layout)
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# Cached loaders
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_resource
def load_models():
    rf_soh     = joblib.load(ARTIFACTS / "rf_soh.pkl")
    rf_rul     = joblib.load(ARTIFACTS / "rf_rul_warning.pkl")
    with open(ARTIFACTS / "feature_meta.json") as f:
        meta = json.load(f)
    return rf_soh, rf_rul, meta


@st.cache_data
def load_data() -> pd.DataFrame:
    return pd.read_csv(DATA_PATH)


# ══════════════════════════════════════════════════════════════════════════════
# Helper: status badge
# ══════════════════════════════════════════════════════════════════════════════

def soh_badge(soh: float) -> tuple[str, str]:
    """Return (label, hex_colour) based on SOH thresholds."""
    if soh >= SOH_WARNING_THRESHOLD:
        return "🟢  GO", GREEN
    elif soh >= SOH_EOL_THRESHOLD:
        return "🟡  CAUTION", YELLOW
    else:
        return "🔴  NO-GO", RED


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2 — Battery Risk
# ══════════════════════════════════════════════════════════════════════════════

def tab_battery(df: pd.DataFrame, rf_soh, rf_rul, meta: dict) -> None:

    SOH_COLS = meta["soh_features"]
    RUL_COLS = meta["rul_features"]

    st.subheader("Battery selector")
    col_sel1, col_sel2 = st.columns([1, 3])

    with col_sel1:
        battery_id = st.selectbox(
            "Battery",
            sorted(df["battery_id"].unique()),
            help="B0005–B0007 were used for training; B0018 is the held-out test cell.",
        )

    bdf = df[df["battery_id"] == battery_id].reset_index(drop=True)

    with col_sel2:
        cycle_idx = st.slider(
            "Discharge cycle",
            min_value=int(bdf["discharge_num"].min()),
            max_value=int(bdf["discharge_num"].max()),
            value=int(bdf["discharge_num"].median()),
            step=1,
        )

    row = bdf[bdf["discharge_num"] == cycle_idx].iloc[0]

    X_soh = pd.DataFrame([row[SOH_COLS]])
    X_rul = pd.DataFrame([row[RUL_COLS]])

    pred_soh   = float(rf_soh.predict(X_soh)[0])
    pred_rul   = float(rf_rul.predict(X_rul)[0])
    actual_soh = float(row["soh"])

    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)

    label, colour = soh_badge(pred_soh)
    m1.metric("Status", label)
    m2.metric(
        "Predicted SOH",
        f"{pred_soh:.1%}",
        delta=f"{pred_soh - actual_soh:+.1%} vs actual",
        delta_color="normal",
    )
    m3.metric("Predicted RUL to 80% warning", f"{max(0, round(pred_rul))} cycles")
    m4.metric("Actual SOH", f"{actual_soh:.1%}")

    st.markdown("---")

    col_left, col_right = st.columns([1.2, 1])

    # Left: SOH degradation — Plotly
    with col_left:
        st.markdown("#### SOH degradation — full history")

        X_all_soh = bdf[SOH_COLS]
        pred_all  = rf_soh.predict(X_all_soh)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=bdf["discharge_num"], y=bdf["soh"],
            mode="lines", name="Actual SOH",
            line=dict(color=BLUE, width=2),
        ))
        fig.add_trace(go.Scatter(
            x=bdf["discharge_num"], y=pred_all,
            mode="lines", name="Predicted SOH",
            line=dict(color=ORANGE, width=2, dash="dash"),
        ))
        fig.add_hline(y=SOH_WARNING_THRESHOLD,
                      line=dict(color=YELLOW, width=1, dash="dot"),
                      annotation_text="80% warning",
                      annotation_position="right",
                      annotation_font_color=YELLOW)
        fig.add_hline(y=SOH_EOL_THRESHOLD,
                      line=dict(color=RED, width=1, dash="dot"),
                      annotation_text="70% EOL",
                      annotation_position="right",
                      annotation_font_color=RED)
        fig.add_vline(x=cycle_idx,
                      line=dict(color="rgba(255,255,255,0.3)", width=1, dash="dash"))
        fig.add_trace(go.Scatter(
            x=[cycle_idx], y=[pred_soh],
            mode="markers", name=f"Cycle {cycle_idx}",
            marker=dict(color=ORANGE, size=10, symbol="circle",
                        line=dict(color="white", width=1.5)),
            hovertemplate=f"Cycle {cycle_idx}<br>Pred SOH: {pred_soh:.1%}<extra></extra>",
        ))
        _apply_layout(fig,
            xaxis_title="Discharge cycle",
            yaxis_title="State of Health",
            yaxis_tickformat=".0%",
            height=340,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Right: SHAP waterfall — stays matplotlib (SHAP lib generates natively)
    with col_right:
        st.markdown("#### Why this prediction? (SHAP waterfall)")

        train_df    = df[df["battery_id"] != "B0018"]
        X_train_soh = train_df[SOH_COLS]
        shap_vals   = compute_shap(rf_soh, X_train_soh, X_soh)

        fig2, ax2 = plt.subplots(figsize=(6, 3.8))
        fig2.patch.set_facecolor("#1A1D2E")
        ax2.set_facecolor("#1A1D2E")
        shap.waterfall_plot(shap_vals[0], show=False)
        plt.title(f"SHAP — cycle {cycle_idx}", fontsize=10,
                  fontweight="bold", pad=8, color="#FAFAFA")
        plt.tight_layout()
        st.pyplot(fig2)
        plt.close()

    explanation = top_drivers(shap_vals, idx=0, n=3)
    st.info(f"**Model explanation:** {explanation}", icon="🔍")

    # RUL trajectory — Plotly
    st.markdown("---")
    st.markdown("#### RUL trajectory — cycles remaining to 80% warning")

    actual_rul   = bdf["rul_warning"].fillna(0)
    pred_rul_all = rf_rul.predict(bdf[RUL_COLS])

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=bdf["discharge_num"], y=actual_rul,
        mode="lines", name="Actual RUL",
        line=dict(color=BLUE, width=2),
        fill="tozeroy", fillcolor="rgba(41,128,185,0.08)",
    ))
    fig3.add_trace(go.Scatter(
        x=bdf["discharge_num"], y=pred_rul_all,
        mode="lines", name="Predicted RUL",
        line=dict(color=ORANGE, width=2, dash="dash"),
    ))
    fig3.add_vline(x=cycle_idx,
                   line=dict(color="rgba(255,255,255,0.3)", width=1, dash="dash"))
    _apply_layout(fig3,
        xaxis_title="Discharge cycle",
        yaxis_title="Cycles remaining",
        height=280,
    )
    st.plotly_chart(fig3, use_container_width=True)

    with st.expander("Raw features for selected cycle"):
        feature_display = row[SOH_COLS].to_frame(name="value").T
        st.dataframe(feature_display.style.format("{:.4f}"))


# ══════════════════════════════════════════════════════════════════════════════
# Tab 1 — Route Energy Risk
# ══════════════════════════════════════════════════════════════════════════════

def _energy_bar(result: FlightResult) -> None:
    """Horizontal stacked bar — Plotly."""
    phases  = ["Hover", "Climb", "Cruise", "Descent", "Safety margin"]
    values  = [
        result.e_hover_wh, result.e_climb_wh,
        result.e_cruise_wh, result.e_descent_wh,
        result.e_with_margin_wh - result.e_total_wh,
    ]
    colours = ["#5B9BD5", "#70AD47", "#ED7D31", "#FFC000", "rgba(192,0,0,0.45)"]

    fig = go.Figure()
    for phase, val, col in zip(phases, values, colours):
        fig.add_trace(go.Bar(
            x=[val], y=["Energy"],
            orientation="h",
            name=f"{phase} ({val:.0f} Wh)",
            marker_color=col,
            text=f"{val:.0f}" if val > 5 else "",
            textposition="inside",
            insidetextanchor="middle",
            hovertemplate=f"{phase}: {val:.0f} Wh<extra></extra>",
        ))

    avail_color = GREEN if result.go else RED
    fig.add_vline(
        x=result.e_available_wh,
        line=dict(color=avail_color, width=2.5, dash="dash"),
        annotation_text=f"Available ({result.e_available_wh:.0f} Wh)",
        annotation_font_color=avail_color,
        annotation_position="top right",
    )

    _apply_layout(fig,
        barmode="stack",
        xaxis_title="Energy [Wh]",
        showlegend=True,
        height=140,
        margin=dict(l=10, r=20, t=30, b=40),
        yaxis=dict(showticklabels=False, gridcolor="rgba(0,0,0,0)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig, use_container_width=True)


def _power_curve_plot(vehicle: VehicleParams, mission: MissionParams,
                      result: FlightResult) -> None:
    """U-shaped power vs speed — Plotly."""
    speeds, powers = power_curve(vehicle, mission.cruise_alt_m, v_max_ms=35.0)
    speeds_kmh = speeds * 3.6
    power_kw   = powers / 1000.0

    idx_endurance = int(np.argmin(powers))
    idx_range     = int(np.argmin(powers / speeds))
    cruise_kw     = result.p_cruise_w / 1000.0

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=speeds_kmh, y=power_kw,
        mode="lines", name="Power curve",
        line=dict(color=BLUE, width=2.5),
        fill="tozeroy", fillcolor="rgba(41,128,185,0.06)",
    ))
    fig.add_vline(x=speeds_kmh[idx_endurance],
                  line=dict(color=GREEN, width=1.5, dash="dot"),
                  annotation_text=f"Best endurance {speeds_kmh[idx_endurance]:.0f} km/h",
                  annotation_font_color=GREEN,
                  annotation_position="top left")
    fig.add_vline(x=speeds_kmh[idx_range],
                  line=dict(color=YELLOW, width=1.5, dash="dot"),
                  annotation_text=f"Best range {speeds_kmh[idx_range]:.0f} km/h",
                  annotation_font_color=YELLOW,
                  annotation_position="top right")
    fig.add_trace(go.Scatter(
        x=[mission.cruise_speed_ms * 3.6], y=[cruise_kw],
        mode="markers",
        name=f"Cruise {mission.cruise_speed_ms*3.6:.0f} km/h · {cruise_kw:.2f} kW",
        marker=dict(color=ORANGE, size=12, symbol="circle",
                    line=dict(color="white", width=1.5)),
        hovertemplate=(f"Cruise: {mission.cruise_speed_ms*3.6:.0f} km/h"
                       f"<br>Power: {cruise_kw:.2f} kW<extra></extra>"),
    ))
    _apply_layout(fig,
        title=dict(text="Power vs speed — momentum theory", font=dict(size=13)),
        xaxis_title="Speed [km/h]",
        yaxis_title="Power [kW]",
        height=320,
    )
    st.plotly_chart(fig, use_container_width=True)


def tab_route(df: pd.DataFrame | None = None, rf_soh=None, meta: dict | None = None) -> None:
    st.subheader("Route Energy Risk — Physics Simulation")
    st.caption(
        "Momentum-theory power model · Glauert forward-flight inflow · "
        "ISA atmosphere · NASA Li-ion cells"
    )

    col_inputs, col_outputs = st.columns([1, 1.6])

    with col_inputs:
        st.markdown("##### 🚁 Vehicle")
        vehicle_mass = st.number_input(
            "Vehicle mass [kg]", min_value=1.0, max_value=500.0,
            value=15.0, step=0.5,
            help="Empty vehicle weight excluding payload and battery.")
        payload = st.number_input(
            "Payload [kg]", min_value=0.0, max_value=200.0,
            value=2.0, step=0.5)
        rotor_area = st.number_input(
            "Total rotor disk area [m²]", min_value=0.05, max_value=50.0,
            value=0.50, step=0.05,
            help="Sum of all rotor disk areas. For 4 × 0.4 m-diameter rotors: ≈ 0.50 m²")
        drag_area = st.number_input(
            "Fuselage drag area [m²]", min_value=0.005, max_value=2.0,
            value=0.020, step=0.005,
            help="Equivalent flat-plate area (Cd × frontal area). Typical: 0.01–0.05 m²")

        st.markdown("##### 🗺️ Mission")
        distance      = st.slider("Route distance [km]", 1.0, 30.0, 5.0, 0.5)
        altitude      = st.slider("Cruise altitude AGL [m]", 20.0, 500.0, 100.0, 10.0)
        speed_ms      = st.slider("Cruise speed [m/s]", 3.0, 30.0, 15.0, 0.5,
                                  help="10 m/s ≈ 36 km/h  ·  20 m/s ≈ 72 km/h")
        safety_margin = st.slider("Safety margin [%]", 5, 40, 15, 1,
                                  help="% of battery capacity reserved.")

        st.markdown("##### 🔋 Battery pack")
        n_cells = st.number_input(
            "Number of cells in pack", min_value=1, max_value=2000,
            value=40, step=1,
            help=f"Each NASA cell = {CELL_ENERGY_WH:.1f} Wh nominal (2 Ah @ 3.6 V).")

        soh_mode = st.radio("SOH source", ["Manual entry", "Link to battery data"],
                            horizontal=True)
        if soh_mode == "Manual entry":
            battery_soh = st.slider("State of Health [%]", 60, 100, 100, 1) / 100.0
        else:
            if df is not None and rf_soh is not None and meta is not None:
                soh_bat = st.selectbox("Battery", sorted(df["battery_id"].unique()),
                                       key="route_bat")
                bdf_r   = df[df["battery_id"] == soh_bat]
                soh_cycle = st.slider(
                    "Discharge cycle",
                    int(bdf_r["discharge_num"].min()),
                    int(bdf_r["discharge_num"].max()),
                    int(bdf_r["discharge_num"].median()),
                    key="route_cycle",
                )
                row_r       = bdf_r[bdf_r["discharge_num"] == soh_cycle].iloc[0]
                X_r         = pd.DataFrame([row_r[meta["soh_features"]]])
                battery_soh = float(rf_soh.predict(X_r)[0])
                st.caption(
                    f"ML-predicted SOH for {soh_bat} cycle {soh_cycle}: "
                    f"**{battery_soh:.1%}**"
                )
            else:
                st.warning("Battery model not loaded — using manual SOH.")
                battery_soh = st.slider("State of Health [%]", 60, 100, 100, 1) / 100.0

    with col_outputs:
        vehicle = VehicleParams(
            vehicle_mass_kg=vehicle_mass,
            payload_kg=payload,
            rotor_disk_area_m2=rotor_area,
            fuselage_drag_area_m2=drag_area,
            n_cells=n_cells,
        )
        mission = MissionParams(
            distance_km=distance,
            cruise_alt_m=altitude,
            cruise_speed_ms=speed_ms,
            safety_margin=safety_margin / 100.0,
        )
        result = simulate_mission(vehicle, mission, battery_soh)

        if result.go:
            st.success(
                f"### 🟢  GO — margin {result.margin_pct:.1%}\n"
                f"Available **{result.e_available_wh:.0f} Wh** · "
                f"Required (incl. {safety_margin}% margin) **{result.e_with_margin_wh:.0f} Wh**"
            )
        else:
            shortage = result.e_with_margin_wh - result.e_available_wh
            st.error(
                f"### 🔴  NO-GO — short by {shortage:.0f} Wh\n"
                f"Available **{result.e_available_wh:.0f} Wh** · "
                f"Required **{result.e_with_margin_wh:.0f} Wh**"
            )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total energy needed", f"{result.e_total_wh:.0f} Wh")
        m2.metric("Pack available", f"{result.e_available_wh:.0f} Wh",
                  delta=f"SOH {battery_soh:.0%}")
        m3.metric("Hover power", f"{result.p_hover_w/1000:.2f} kW")
        m4.metric("Est. max range", f"{result.max_range_km:.1f} km",
                  help="At best-range speed with current battery SOH.")

        st.markdown("#### Energy budget by flight phase")
        _energy_bar(result)

        phase_df = pd.DataFrame({
            "Phase":       ["Hover", "Climb", "Cruise", "Descent"],
            "Time [s]":    [f"{result.t_hover_s:.0f}", f"{result.t_climb_s:.0f}",
                            f"{result.t_cruise_s:.0f}", f"{result.t_descent_s:.0f}"],
            "Power [W]":   [f"{result.p_hover_w:.0f}", f"{result.p_climb_w:.0f}",
                            f"{result.p_cruise_w:.0f}", f"{result.p_descent_w:.0f}"],
            "Energy [Wh]": [f"{result.e_hover_wh:.1f}", f"{result.e_climb_wh:.1f}",
                            f"{result.e_cruise_wh:.1f}", f"{result.e_descent_wh:.1f}"],
        })
        st.dataframe(phase_df, hide_index=True, use_container_width=True)

        st.markdown("#### Power vs speed — the U-shaped curve")
        st.caption(
            "Induced power decreases with speed (larger air mass swept); "
            "parasitic drag grows as V³. Their sum creates a minimum. "
            "Best endurance = minimum power. Best range = minimum power-per-metre."
        )
        _power_curve_plot(vehicle, mission, result)

        with st.expander("Model assumptions & limitations"):
            st.markdown("""
**Momentum theory** (Glauert, 1935) gives induced power in forward flight by solving
the inflow equation `v_i⁴ + V² v_i² − v_h⁴ = 0`, where `v_h` is the hover-induced velocity.

**Three power components:**
- **Induced**: energy to accelerate air downward; dominant at low speed; decreases with V.
- **Profile**: rotor blade drag; ≈ constant at ~6% of hover power for multirotors.
- **Parasitic**: fuselage drag = ½ ρ Cd A V³; dominates at high speed.

**Efficiency factor κ = 1.15** accounts for tip losses and non-uniform inflow (real rotors
are ~87% efficient vs. ideal momentum theory).

**Not modelled:** wind, ground effect, battery discharge curve, motor/ESC losses,
rotor tilt angle in forward flight.
            """)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3 — Operating Regime Explorer
# ══════════════════════════════════════════════════════════════════════════════

REGIME_COLOURS  = ["#2ECC71", "#3498DB", "#F39C12", "#E67E22", "#E74C3C", "#8E44AD"]
BATTERY_MARKERS = {
    "B0005": "circle",
    "B0006": "square",
    "B0007": "triangle-up",
    "B0018": "diamond",
}


@st.cache_data
def _run_regime_analysis(feature_tuple: tuple, n_clusters: int | None) -> dict:
    df = pd.read_csv(
        Path(__file__).resolve().parent.parent / "data" / "processed" / "battery_features.csv"
    )
    result = fit_regimes(df, feature_cols=list(feature_tuple), n_clusters=n_clusters)
    return result


def tab_regime(df: pd.DataFrame) -> None:
    st.subheader("Operating Regime Explorer")
    st.caption(
        "PCA reduces 8 cycle features to 2 axes of maximum variance. "
        "GMM clusters those axes into operating regimes. "
        "Regimes are ordered left → right from healthiest to most degraded."
    )

    col_ctrl, col_main = st.columns([1, 2.2])

    with col_ctrl:
        st.markdown("##### Features")
        available = [f for f in DEFAULT_FEATURES if f in df.columns]
        selected  = st.multiselect(
            "Include in clustering",
            options=available,
            default=available,
            format_func=lambda f: FEATURE_LABELS.get(f, f),
        )
        if len(selected) < 2:
            st.warning("Select at least 2 features.")
            return

        st.markdown("##### Regimes")
        auto_k     = st.checkbox("Auto-select K via BIC", value=True)
        n_clusters = None
        if not auto_k:
            n_clusters = st.slider("Number of regimes (K)", 2, 6, 4)

        st.markdown("##### Overlay")
        highlight_bat = st.selectbox(
            "Show trajectory for battery",
            ["None"] + sorted(df["battery_id"].unique().tolist()),
        )
        show_ellipses = st.checkbox("Show cluster ellipses", value=True)

    with st.spinner("Fitting PCA + GMM…"):
        result = _run_regime_analysis(tuple(sorted(selected)), n_clusters)

    dfo = result.df_out
    K   = result.n_clusters

    # ── Main PCA scatter — Plotly ─────────────────────────────────────────────
    with col_main:
        st.markdown(f"#### PCA space — {K} operating regimes")

        fig = go.Figure()

        # Cluster ellipses
        if show_ellipses:
            for r in range(K):
                sub = dfo[dfo["regime"] == r]
                if len(sub) < 3:
                    continue
                cov        = np.cov(sub["pc1"], sub["pc2"])
                vals, vecs = np.linalg.eigh(cov)
                order_v    = vals.argsort()[::-1]
                vals, vecs = vals[order_v], vecs[:, order_v]
                angle_rad  = np.arctan2(*vecs[:, 0][::-1])
                w, h       = np.sqrt(vals)
                theta      = np.linspace(0, 2 * np.pi, 80)
                ex = w * np.cos(theta)
                ey = h * np.sin(theta)
                cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
                cx = sub["pc1"].mean() + cos_a * ex - sin_a * ey
                cy = sub["pc2"].mean() + sin_a * ex + cos_a * ey
                hex_c   = REGIME_COLOURS[r % len(REGIME_COLOURS)].lstrip("#")
                rr, gg, bb = int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)
                fig.add_trace(go.Scatter(
                    x=cx, y=cy, mode="lines", showlegend=False,
                    line=dict(color=REGIME_COLOURS[r % len(REGIME_COLOURS)],
                              width=1.5, dash="dash"),
                    fill="toself",
                    fillcolor=f"rgba({rr},{gg},{bb},0.08)",
                    hoverinfo="skip",
                ))

        # Scatter points
        for bat, marker in BATTERY_MARKERS.items():
            sub_bat = dfo[dfo["battery_id"] == bat]
            if sub_bat.empty:
                continue
            for r in range(K):
                sub = sub_bat[sub_bat["regime"] == r]
                if sub.empty:
                    continue
                fig.add_trace(go.Scatter(
                    x=sub["pc1"], y=sub["pc2"],
                    mode="markers",
                    name=f"{bat} – R{r}",
                    legendgroup=f"regime_{r}",
                    showlegend=(bat == list(BATTERY_MARKERS.keys())[0]),
                    marker=dict(
                        color=REGIME_COLOURS[r % len(REGIME_COLOURS)],
                        symbol=marker, size=7, opacity=0.75,
                        line=dict(width=0),
                    ),
                    hovertemplate=(f"{bat} · R{r}<br>"
                                   f"PC1: %{{x:.2f}}<br>PC2: %{{y:.2f}}<extra></extra>"),
                ))

        # Trajectory overlay
        if highlight_bat != "None":
            traj = dfo[dfo["battery_id"] == highlight_bat].sort_values("discharge_num")
            fig.add_trace(go.Scatter(
                x=traj["pc1"], y=traj["pc2"],
                mode="lines", name=f"{highlight_bat} trajectory",
                line=dict(color="rgba(255,255,255,0.4)", width=1),
            ))
            fig.add_trace(go.Scatter(
                x=[traj["pc1"].iloc[0]], y=[traj["pc2"].iloc[0]],
                mode="markers", name="First cycle",
                marker=dict(color="white", size=10, symbol="star"),
            ))
            fig.add_trace(go.Scatter(
                x=[traj["pc1"].iloc[-1]], y=[traj["pc2"].iloc[-1]],
                mode="markers", name="Last cycle",
                marker=dict(color="white", size=10, symbol="x"),
            ))

        # Regime centroid labels
        annotations = []
        for r in range(K):
            sub = dfo[dfo["regime"] == r]
            annotations.append(dict(
                x=sub["pc1"].mean(), y=sub["pc2"].mean(),
                text=f"<b>R{r}</b>",
                showarrow=False,
                font=dict(color=REGIME_COLOURS[r % len(REGIME_COLOURS)], size=13),
                bgcolor="rgba(15,17,23,0.7)",
                borderpad=3,
            ))

        ev = result.explained_variance
        _apply_layout(fig,
            xaxis_title=(f"PC1 — degradation axis  ({ev[0]:.0%} variance)"
                         "  ← healthier · more degraded →"),
            yaxis_title=f"PC2 — thermal/voltage axis  ({ev[1]:.0%} variance)",
            annotations=annotations,
            height=480,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Bottom row: BIC + explained variance + regime table ───────────────────
    st.markdown("---")
    c1, c2, c3 = st.columns([1, 1, 1.4])

    with c1:
        st.markdown("#### BIC — model selection")
        st.caption("Lower = better fit for the complexity used.")
        ks   = list(result.bic_scores.keys())
        bics = list(result.bic_scores.values())
        best = min(result.bic_scores, key=result.bic_scores.get)

        fig_bic = go.Figure()
        fig_bic.add_trace(go.Scatter(
            x=ks, y=bics, mode="lines+markers",
            line=dict(color=BLUE, width=2),
            marker=dict(size=7, color=BLUE),
            name="BIC",
        ))
        fig_bic.add_trace(go.Scatter(
            x=[best], y=[result.bic_scores[best]],
            mode="markers", name=f"Best K={best}",
            marker=dict(color=GREEN, size=12, symbol="circle"),
        ))
        _apply_layout(fig_bic,
            xaxis_title="K (regimes)", yaxis_title="BIC",
            height=240, margin=dict(l=50, r=20, t=20, b=50),
        )
        st.plotly_chart(fig_bic, use_container_width=True)

    with c2:
        st.markdown("#### PCA — explained variance")
        st.caption("How much information each component captures.")
        pcs    = [f"PC{i+1}" for i in range(len(result.explained_variance))]
        ev_pct = result.explained_variance * 100

        fig_ev = go.Figure(go.Bar(
            x=pcs, y=ev_pct,
            marker_color=[BLUE, GREEN],
            text=[f"{v:.0f}%" for v in ev_pct],
            textposition="outside",
        ))
        _apply_layout(fig_ev,
            yaxis_title="Variance explained (%)",
            yaxis_range=[0, max(ev_pct) * 1.3],
            height=240, margin=dict(l=50, r=20, t=20, b=50),
            showlegend=False,
        )
        st.plotly_chart(fig_ev, use_container_width=True)

    with c3:
        st.markdown("#### Regime summary")
        summary = regime_summary(result)
        st.dataframe(
            summary.style.apply(
                lambda col: [
                    f"background-color: {REGIME_COLOURS[i % len(REGIME_COLOURS)]}22"
                    for i in range(len(col))
                ], axis=0
            ),
            hide_index=True, use_container_width=True,
        )

    with st.expander("PCA loadings — what each axis means physically"):
        st.caption(
            "Each value shows how strongly a feature contributes to that PC. "
            "PC1 loads heavily on cycle number (+), voltage (−) and duration (−): "
            "it is the **degradation axis**. High PC1 = older, more degraded cell."
        )
        loadings_display = result.loadings.copy()
        loadings_display.index = [FEATURE_LABELS.get(f, f) for f in loadings_display.index]
        st.dataframe(
            loadings_display.style.background_gradient(
                cmap="RdBu_r", vmin=-1, vmax=1, axis=None),
            use_container_width=True,
        )

    with st.expander("Cluster profiles — mean feature values per regime"):
        st.caption(
            "Standardised (z-score) mean feature value per regime. "
            "Red = above average, blue = below average."
        )
        cp = result.cluster_profiles.copy()
        cp.columns = [FEATURE_LABELS.get(f, f) for f in cp.columns]
        st.dataframe(
            cp.style.background_gradient(cmap="RdBu_r", axis=None),
            use_container_width=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Main layout
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    st.title("⚡ Polaris Fleet Energy & Battery Risk Studio")
    st.caption(
        "NASA PCoE lithium-ion dataset · Random Forest + SHAP · "
        "Research preview — not for operational use"
    )

    try:
        rf_soh, rf_rul, meta = load_models()
        df = load_data()
    except FileNotFoundError as e:
        st.error(
            f"Could not load model artifacts: {e}\n\n"
            "Run `notebooks/04_model_training.ipynb` first to generate the "
            "`.pkl` files in `outputs/model_artifacts/`."
        )
        st.stop()

    tab1, tab2, tab3 = st.tabs([
        "🚁 Route Energy Risk",
        "🔋 Battery Risk",
        "🗺️ Operating Regime Explorer",
    ])

    with tab1:
        tab_route(df, rf_soh, meta)

    with tab2:
        tab_battery(df, rf_soh, rf_rul, meta)

    with tab3:
        tab_regime(df)


if __name__ == "__main__":
    main()
