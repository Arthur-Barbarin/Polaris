"""
Polaris Fleet Energy & Battery Risk Studio
===========================================
Streamlit dashboard — 3 tabs

  Tab 1 — Route Energy Risk     ← physics-informed energy simulation
  Tab 2 — Battery Risk          ← live ML predictions + SHAP
  Tab 3 — Operating Regime      (coming soon — PCA / GMM clustering)

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
import shap
import streamlit as st

from battery_features import SOH_WARNING_THRESHOLD, SOH_EOL_THRESHOLD
from explainability import compute_shap, top_drivers
from route_simulation import (
    VehicleParams, MissionParams, FlightResult,
    simulate_mission, power_curve, CELL_ENERGY_WH,
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

    # ── Sidebar-style controls (rendered inline, top of tab) ──────────────────
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

    # ── Build feature vectors ─────────────────────────────────────────────────
    X_soh = pd.DataFrame([row[SOH_COLS]])
    X_rul = pd.DataFrame([row[RUL_COLS]])

    pred_soh = float(rf_soh.predict(X_soh)[0])
    pred_rul = float(rf_rul.predict(X_rul)[0])
    actual_soh = float(row["soh"])

    # ── Top metric row ────────────────────────────────────────────────────────
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

    # ── Two-column layout: SOH history + SHAP waterfall ───────────────────────
    col_left, col_right = st.columns([1.2, 1])

    # Left: SOH degradation curve with current position marker
    with col_left:
        st.markdown("#### SOH degradation — full history")
        fig, ax = plt.subplots(figsize=(7, 3.5))

        ax.plot(bdf["discharge_num"], bdf["soh"],
                color=BLUE, linewidth=1.8, label="Actual SOH")

        # Predicted SOH for every cycle (for the trajectory overlay)
        X_all_soh = bdf[SOH_COLS]
        pred_all   = rf_soh.predict(X_all_soh)
        ax.plot(bdf["discharge_num"], pred_all,
                color="darkorange", linewidth=1.5,
                linestyle="--", label="Predicted SOH")

        # Threshold lines
        ax.axhline(SOH_WARNING_THRESHOLD, color=YELLOW, linewidth=1,
                   linestyle=":", label="80% warning")
        ax.axhline(SOH_EOL_THRESHOLD, color=RED, linewidth=1,
                   linestyle=":", label="70% EOL")

        # Current cycle marker
        ax.axvline(cycle_idx, color="grey", linewidth=1, linestyle="--", alpha=0.7)
        ax.scatter([cycle_idx], [pred_soh], color="darkorange",
                   s=60, zorder=5, label=f"Selected cycle ({cycle_idx})")

        ax.set_xlabel("Discharge cycle", fontsize=9)
        ax.set_ylabel("State of Health", fontsize=9)
        ax.yaxis.set_major_formatter(
            plt.matplotlib.ticker.PercentFormatter(xmax=1.0))
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(True, alpha=0.25)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()

    # Right: SHAP waterfall for the selected cycle
    with col_right:
        st.markdown("#### Why this prediction? (SHAP waterfall)")

        # We need a background set for the explainer — use the training batteries
        train_df = df[df["battery_id"] != "B0018"]
        X_train_soh = train_df[SOH_COLS]

        shap_vals = compute_shap(rf_soh, X_train_soh, X_soh)

        fig2, ax2 = plt.subplots(figsize=(6, 3.8))
        shap.waterfall_plot(shap_vals[0], show=False)
        plt.title(f"SHAP — cycle {cycle_idx}", fontsize=10,
                  fontweight="bold", pad=8)
        plt.tight_layout()
        st.pyplot(fig2)
        plt.close()

    # ── Explanation text ──────────────────────────────────────────────────────
    explanation = top_drivers(shap_vals, idx=0, n=3)
    st.info(f"**Model explanation:** {explanation}", icon="🔍")

    # ── RUL trajectory ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### RUL trajectory — cycles remaining to 80% warning")

    fig3, ax3 = plt.subplots(figsize=(10, 3))
    actual_rul = bdf["rul_warning"].fillna(0)
    pred_rul_all = rf_rul.predict(bdf[RUL_COLS])

    ax3.plot(bdf["discharge_num"], actual_rul,
             color=BLUE, linewidth=1.5, label="Actual RUL")
    ax3.plot(bdf["discharge_num"], pred_rul_all,
             color="darkorange", linestyle="--", linewidth=1.5,
             label="Predicted RUL")
    ax3.axvline(cycle_idx, color="grey", linewidth=1,
                linestyle="--", alpha=0.7)
    ax3.set_xlabel("Discharge cycle", fontsize=9)
    ax3.set_ylabel("Cycles remaining", fontsize=9)
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.25)
    plt.tight_layout()
    st.pyplot(fig3)
    plt.close()

    # ── Raw feature table for selected cycle ─────────────────────────────────
    with st.expander("Raw features for selected cycle"):
        feature_display = row[SOH_COLS].to_frame(name="value").T
        st.dataframe(feature_display.style.format("{:.4f}"))


# ══════════════════════════════════════════════════════════════════════════════
# Tab 1 — Route Energy Risk
# ══════════════════════════════════════════════════════════════════════════════

def _energy_bar(result: FlightResult) -> None:
    """Horizontal stacked bar: energy by flight phase + safety margin."""
    phases = ["Hover", "Climb", "Cruise", "Descent"]
    values = [result.e_hover_wh, result.e_climb_wh,
              result.e_cruise_wh, result.e_descent_wh]
    colours = ["#5B9BD5", "#70AD47", "#ED7D31", "#FFC000"]

    fig, ax = plt.subplots(figsize=(9, 1.6))
    left = 0.0
    for phase, val, col in zip(phases, values, colours):
        ax.barh(0, val, left=left, color=col, label=f"{phase} ({val:.0f} Wh)", height=0.5)
        if val > 5:
            ax.text(left + val / 2, 0, f"{val:.0f}", ha="center", va="center",
                    fontsize=8, color="white", fontweight="bold")
        left += val

    # Safety margin band
    margin_val = result.e_with_margin_wh - result.e_total_wh
    ax.barh(0, margin_val, left=left, color="#C00000", alpha=0.4,
            label=f"Safety margin ({margin_val:.0f} Wh)", height=0.5)
    left += margin_val

    # Available capacity line
    ax.axvline(result.e_available_wh, color="#2ECC71" if result.go else "#E74C3C",
               linewidth=2.5, linestyle="--",
               label=f"Available ({result.e_available_wh:.0f} Wh)")

    ax.set_xlim(0, max(result.e_available_wh, result.e_with_margin_wh) * 1.08)
    ax.set_yticks([])
    ax.set_xlabel("Energy [Wh]", fontsize=9)
    ax.legend(loc="upper right", fontsize=7.5, ncol=3)
    ax.grid(True, axis="x", alpha=0.3)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()


def _power_curve_plot(vehicle: VehicleParams, mission: MissionParams,
                      result: FlightResult) -> None:
    """U-shaped power vs speed curve with operating point and optimal speeds marked."""
    speeds, powers = power_curve(vehicle, mission.cruise_alt_m, v_max_ms=35.0)
    power_kw = powers / 1000.0

    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.plot(speeds * 3.6, power_kw, color=BLUE, linewidth=2.0)

    # Best endurance speed (min power)
    idx_endurance = np.argmin(powers)
    ax.axvline(speeds[idx_endurance] * 3.6, color=GREEN, linewidth=1.2,
               linestyle=":", alpha=0.9,
               label=f"Best endurance {speeds[idx_endurance]*3.6:.0f} km/h")

    # Best range speed (min P/V)
    idx_range = np.argmin(powers / speeds)
    ax.axvline(speeds[idx_range] * 3.6, color=YELLOW, linewidth=1.2,
               linestyle=":", alpha=0.9,
               label=f"Best range {speeds[idx_range]*3.6:.0f} km/h")

    # Current cruise point
    cruise_kw = result.p_cruise_w / 1000.0
    ax.scatter([mission.cruise_speed_ms * 3.6], [cruise_kw],
               color="darkorange", s=70, zorder=5,
               label=f"Your cruise {mission.cruise_speed_ms*3.6:.0f} km/h · {cruise_kw:.2f} kW")

    ax.set_xlabel("Speed [km/h]", fontsize=9)
    ax.set_ylabel("Power [kW]", fontsize=9)
    ax.set_title("Power vs speed — momentum theory", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()


def tab_route(df: pd.DataFrame | None = None, rf_soh=None, meta: dict | None = None) -> None:
    """
    Route Energy Risk tab.

    Architecture
    ------------
    Left column  : mission + vehicle inputs (sliders / number inputs)
    Right column : simulation outputs (GO/NO-GO, energy chart, power curve)

    The battery SOH can be linked to a real battery from the dataset
    (uses the trained RF model from Tab 2) or entered manually.
    """

    st.subheader("Route Energy Risk — Physics Simulation")
    st.caption(
        "Momentum-theory power model · Glauert forward-flight inflow · "
        "ISA atmosphere · NASA Li-ion cells"
    )

    col_inputs, col_outputs = st.columns([1, 1.6])

    # ── LEFT: inputs ──────────────────────────────────────────────────────────
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
        distance = st.slider("Route distance [km]", 1.0, 30.0, 5.0, 0.5)
        altitude  = st.slider("Cruise altitude AGL [m]", 20.0, 500.0, 100.0, 10.0)
        speed_ms  = st.slider(
            "Cruise speed [m/s]", 3.0, 30.0, 15.0, 0.5,
            help="10 m/s ≈ 36 km/h  ·  20 m/s ≈ 72 km/h")
        safety_margin = st.slider(
            "Safety margin [%]", 5, 40, 15, 1,
            help="% of battery capacity reserved — not counted toward usable energy.")

        st.markdown("##### 🔋 Battery pack")
        n_cells = st.number_input(
            "Number of cells in pack", min_value=1, max_value=2000,
            value=40, step=1,
            help=f"Each NASA cell = {CELL_ENERGY_WH:.1f} Wh nominal (2 Ah @ 3.6 V).")

        # SOH source
        soh_mode = st.radio(
            "SOH source",
            ["Manual entry", "Link to battery data"],
            horizontal=True,
        )
        if soh_mode == "Manual entry":
            battery_soh = st.slider("State of Health [%]", 60, 100, 100, 1) / 100.0
        else:
            if df is not None and rf_soh is not None and meta is not None:
                soh_bat = st.selectbox(
                    "Battery", sorted(df["battery_id"].unique()), key="route_bat")
                bdf_r = df[df["battery_id"] == soh_bat]
                soh_cycle = st.slider(
                    "Discharge cycle",
                    int(bdf_r["discharge_num"].min()),
                    int(bdf_r["discharge_num"].max()),
                    int(bdf_r["discharge_num"].median()),
                    key="route_cycle",
                )
                row_r = bdf_r[bdf_r["discharge_num"] == soh_cycle].iloc[0]
                X_r = pd.DataFrame([row_r[meta["soh_features"]]])
                battery_soh = float(rf_soh.predict(X_r)[0])
                st.caption(
                    f"ML-predicted SOH for {soh_bat} cycle {soh_cycle}: "
                    f"**{battery_soh:.1%}**"
                )
            else:
                st.warning("Battery model not loaded — using manual SOH.")
                battery_soh = st.slider("State of Health [%]", 60, 100, 100, 1) / 100.0

    # ── RIGHT: outputs ────────────────────────────────────────────────────────
    with col_outputs:

        # Build parameter objects and run simulation
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

        # ── GO / NO-GO banner ─────────────────────────────────────────────────
        total_mass = vehicle_mass + payload
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

        # ── Key metrics ───────────────────────────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total energy needed", f"{result.e_total_wh:.0f} Wh")
        m2.metric("Pack available", f"{result.e_available_wh:.0f} Wh",
                  delta=f"SOH {battery_soh:.0%}")
        m3.metric("Hover power", f"{result.p_hover_w/1000:.2f} kW")
        m4.metric("Est. max range", f"{result.max_range_km:.1f} km",
                  help="At best-range speed with current battery SOH.")

        # ── Energy budget bar ─────────────────────────────────────────────────
        st.markdown("#### Energy budget by flight phase")
        _energy_bar(result)

        # ── Phase breakdown table ─────────────────────────────────────────────
        phase_df = pd.DataFrame({
            "Phase":     ["Hover", "Climb", "Cruise", "Descent"],
            "Time [s]":  [f"{result.t_hover_s:.0f}", f"{result.t_climb_s:.0f}",
                          f"{result.t_cruise_s:.0f}", f"{result.t_descent_s:.0f}"],
            "Power [W]": [f"{result.p_hover_w:.0f}", f"{result.p_climb_w:.0f}",
                          f"{result.p_cruise_w:.0f}", f"{result.p_descent_w:.0f}"],
            "Energy [Wh]": [f"{result.e_hover_wh:.1f}", f"{result.e_climb_wh:.1f}",
                            f"{result.e_cruise_wh:.1f}", f"{result.e_descent_wh:.1f}"],
        })
        st.dataframe(phase_df, hide_index=True, use_container_width=True)

        # ── Power vs speed curve ──────────────────────────────────────────────
        st.markdown("#### Power vs speed — the U-shaped curve")
        st.caption(
            "Induced power decreases with speed (larger air mass swept); "
            "parasitic drag grows as V³. Their sum creates a minimum. "
            "Best endurance = minimum power. Best range = minimum power-per-metre."
        )
        _power_curve_plot(vehicle, mission, result)

        # ── Physics note ──────────────────────────────────────────────────────
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
rotor tilt angle in forward flight (this model assumes the rotor disk stays horizontal,
which slightly underestimates power at high cruise speeds).
            """)



# ══════════════════════════════════════════════════════════════════════════════
# Tab 3 — Operating Regime Explorer (stub)
# ══════════════════════════════════════════════════════════════════════════════

def tab_regime() -> None:
    st.subheader("Operating Regime Explorer")
    st.info(
        "**Coming soon.** This tab will apply PCA + Gaussian Mixture Models "
        "to cluster discharge cycles into operating regimes "
        "(e.g. high-load/hot, normal, cold-start) and show which regime "
        "each battery spends most of its life in.",
        icon="🗺️",
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

    # Load assets
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
        tab_regime()


if __name__ == "__main__":
    main()
