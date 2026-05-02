"""
evaluation.py
-------------
Regression evaluation metrics and diagnostic plots for the
Polaris battery degradation pipeline.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


# ── Metrics ───────────────────────────────────────────────────────────────────

def evaluate_regression(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray,
    model_name: str = "Model",
    target_name: str = "SOH",
) -> dict:
    """
    Compute and print MAE, RMSE, and R² for a regression model.

    Why these three metrics?
    - MAE  : average absolute error — easy to interpret in the original unit
              (e.g. 0.01 SOH = 1 percentage point off on average).
    - RMSE : penalises large errors more than MAE — useful to catch if the
              model occasionally makes catastrophic predictions.
    - R²   : fraction of variance explained — 1.0 is perfect, 0.0 means the
              model does no better than predicting the mean.

    Returns
    -------
    dict with keys 'model', 'target', 'MAE', 'RMSE', 'R2'.
    """
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)

    mae  = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2   = r2_score(y_true, y_pred)

    print(f"\n{'─'*40}")
    print(f"  {model_name}  [{target_name}]")
    print(f"  MAE  = {mae:.5f}")
    print(f"  RMSE = {rmse:.5f}")
    print(f"  R²   = {r2:.5f}")
    print(f"{'─'*40}")

    return {"model": model_name, "target": target_name,
            "MAE": mae, "RMSE": rmse, "R2": r2}


def compare_models(results: list[dict]) -> pd.DataFrame:
    """Pretty-print a comparison table from a list of evaluate_regression dicts."""
    df = pd.DataFrame(results).set_index("model")
    print("\nModel comparison:")
    print(df.round(5).to_string())
    return df


# ── Diagnostic plots ──────────────────────────────────────────────────────────

def plot_actual_vs_predicted(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray,
    model_name: str = "Model",
    target_name: str = "SOH",
    discharge_nums: np.ndarray | None = None,
    save_path: str | Path | None = None,
) -> None:
    """
    Two-panel plot:
      Top   — actual vs predicted over discharge cycles (time series view)
      Bottom — actual vs predicted scatter with perfect-fit diagonal

    The time-series view reveals whether errors are systematic at certain
    stages of degradation (e.g. the model might be accurate early but drift
    near end-of-life — important to know before deploying).
    """
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    x_axis = discharge_nums if discharge_nums is not None else np.arange(len(y_true))

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # ── Left: time-series ─────────────────────────────────────────────────────
    ax = axes[0]
    ax.plot(x_axis, y_true, label="Actual",    color="steelblue",  linewidth=1.5)
    ax.plot(x_axis, y_pred, label="Predicted", color="darkorange",
            linewidth=1.5, linestyle="--")
    ax.fill_between(x_axis, y_true, y_pred, alpha=0.15, color="darkorange",
                    label="Error")
    ax.set_xlabel("Discharge cycle", fontsize=10)
    ax.set_ylabel(target_name, fontsize=10)
    ax.set_title(f"{model_name} — {target_name} over cycles (test battery)", fontsize=11)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0))
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # ── Right: scatter ────────────────────────────────────────────────────────
    ax = axes[1]
    ax.scatter(y_true, y_pred, s=12, alpha=0.6, color="steelblue")
    lims = [min(y_true.min(), y_pred.min()) - 0.02,
            max(y_true.max(), y_pred.max()) + 0.02]
    ax.plot(lims, lims, "k--", linewidth=1, label="Perfect fit")
    ax.set_xlabel(f"Actual {target_name}", fontsize=10)
    ax.set_ylabel(f"Predicted {target_name}", fontsize=10)
    ax.set_title(f"{model_name} — Actual vs Predicted scatter", fontsize=11)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0))
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Figure saved → {save_path}")
    plt.show()


def plot_residuals(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray,
    model_name: str = "Model",
    discharge_nums: np.ndarray | None = None,
    save_path: str | Path | None = None,
) -> None:
    """
    Residual plot: (predicted - actual) vs cycle number.

    A good model should show residuals scattered randomly around 0 with no
    systematic trend. If residuals drift (e.g. consistently positive late in
    life), the model is biased in that region.
    """
    y_true    = np.array(y_true)
    residuals = y_pred - np.array(y_true)
    x_axis    = discharge_nums if discharge_nums is not None else np.arange(len(y_true))

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.scatter(x_axis, residuals, s=10, alpha=0.6, color="steelblue")
    ax.axhline(0, color="red", linewidth=1, linestyle="--")
    ax.set_xlabel("Discharge cycle", fontsize=10)
    ax.set_ylabel("Residual (predicted − actual)", fontsize=10)
    ax.set_title(f"{model_name} — Residuals", fontsize=11)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Figure saved → {save_path}")
    plt.show()
