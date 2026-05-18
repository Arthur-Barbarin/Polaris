"""
explainability.py
-----------------
SHAP-based explainability for the Polaris battery degradation models.

Why SHAP?
---------
Feature importance from sklearn (mean impurity decrease) tells you which
features the forest uses most on average, but it is biased toward high-
cardinality features and gives no information about direction or magnitude
for individual predictions.

SHAP (SHapley Additive exPlanations) is grounded in game theory:
for each prediction, it assigns each feature a contribution value that
satisfies additivity — the sum of all SHAP values equals the difference
between the prediction and the global mean prediction. This means:

  - You can explain *any individual prediction*, not just global averages.
  - Direction is explicit: positive SHAP = pushes SOH up, negative = pushes down.
  - It is model-agnostic in principle, but TreeExplainer is exact and fast
    for tree-based models (no sampling needed).

This is what you would show in a Polaris client demo:
"The model predicts this battery has 40 cycles remaining. The main reason
is that its mean discharge voltage has dropped to 3.44 V (–0.08 SHAP) and
it has already completed 120 cycles (–0.06 SHAP)."
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap


# ── SHAP computation ──────────────────────────────────────────────────────────

def compute_shap(
    model,
    X_train: pd.DataFrame,
    X_explain: pd.DataFrame,
) -> shap.Explanation:
    """
    Compute SHAP values using TreeExplainer (exact, fast for Random Forests).

    Parameters
    ----------
    model     : fitted RandomForestRegressor
    X_train   : training features — used to set the background distribution
    X_explain : features to explain (typically the test set)

    Returns
    -------
    shap.Explanation  — contains .values (SHAP array), .base_values, .data
    """
    explainer   = shap.TreeExplainer(model, X_train)
    shap_values = explainer(X_explain)
    return shap_values


# ── SHAP plots ────────────────────────────────────────────────────────────────

def plot_shap_summary(
    shap_values: shap.Explanation,
    title: str = "SHAP Summary — Feature Impact on SOH",
    save_path: str | Path | None = None,
    max_display: int = 10,
) -> None:
    """
    Beeswarm summary plot: one dot per sample, x-axis = SHAP value,
    colour = feature value (red = high, blue = low).

    How to read it:
    - Features are ranked by mean |SHAP| (most important at the top).
    - Each dot is one discharge cycle in the test set.
    - A dot to the right means that sample's feature value pushes SOH UP.
    - Colour tells you *which direction* the feature value is going:
      red dots on the right → high feature value increases predicted SOH.
    """
    plt.figure(figsize=(9, 5))
    shap.summary_plot(
        shap_values,
        max_display=max_display,
        show=False,
        plot_size=None,
    )
    plt.title(title, fontsize=12, fontweight="bold", pad=12)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Figure saved → {save_path}")
    plt.show()


def plot_shap_bar(
    shap_values: shap.Explanation,
    title: str = "Mean |SHAP| — Global Feature Importance",
    save_path: str | Path | None = None,
    max_display: int = 10,
) -> None:
    """
    Bar plot of mean absolute SHAP values — the simplest way to
    communicate 'which features matter most' to a non-technical client.
    """
    plt.figure(figsize=(8, 4))
    shap.summary_plot(
        shap_values,
        plot_type="bar",
        max_display=max_display,
        show=False,
        plot_size=None,
    )
    plt.title(title, fontsize=12, fontweight="bold", pad=12)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Figure saved → {save_path}")
    plt.show()


def plot_shap_waterfall(
    shap_values: shap.Explanation,
    idx: int = 0,
    title: str | None = None,
    save_path: str | Path | None = None,
) -> None:
    """
    Waterfall plot for a single prediction — shows how each feature
    pushes the prediction above or below the baseline (mean SOH).

    This is the plot you would use in a Polaris dashboard to explain
    *why* a specific battery cycle was flagged as high-risk.

    Parameters
    ----------
    idx : index of the sample to explain (within the explanation set)
    """
    _title = title or f"SHAP Waterfall — sample index {idx}"
    plt.figure(figsize=(9, 5))
    shap.waterfall_plot(shap_values[idx], show=False)
    plt.title(_title, fontsize=11, fontweight="bold", pad=12)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Figure saved → {save_path}")
    plt.show()


# ── Text explanation helper ───────────────────────────────────────────────────

def top_drivers(
    shap_values: shap.Explanation,
    idx: int,
    n: int = 3,
) -> str:
    """
    Return a human-readable string listing the top n SHAP drivers
    for a single prediction.

    Example output:
      "Risk driven by: mean_discharge_voltage (↓ –0.042),
       discharge_num (↓ –0.031), discharge_duration (↓ –0.018)"

    Used in the Streamlit dashboard to generate the explanation text
    beneath the go/caution/no-go badge.
    """
    sv   = shap_values.values[idx]
    feat = shap_values.feature_names
    data = shap_values.data[idx]

    # Sort by absolute SHAP, take top n
    order = np.argsort(np.abs(sv))[::-1][:n]

    parts = []
    for i in order:
        arrow = "↑" if sv[i] > 0 else "↓"
        parts.append(f"{feat[i]} ({arrow} {sv[i]:+.3f})")

    return "Risk driven by: " + ", ".join(parts)
