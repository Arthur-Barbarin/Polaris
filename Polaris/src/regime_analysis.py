"""
regime_analysis.py
------------------
Unsupervised operating-regime discovery for the Polaris battery pipeline.

Why PCA + GMM?
--------------
Each discharge cycle is described by 8 numeric features (voltage, temperature,
duration, age, etc.). That's an 8-dimensional space — impossible to visualise
directly. We use two steps:

  1. PCA (Principal Component Analysis)
     Rotates the feature space to find the directions of maximum variance.
     The first two principal components capture most of the spread in the data
     and can be plotted as a 2-D scatter.

     Crucially, the loadings (how each original feature maps onto each PC) tell
     you what the axes *mean* physically — e.g. PC1 ≈ "degradation level",
     PC2 ≈ "thermal operating condition".

  2. GMM (Gaussian Mixture Model)
     Fits K multivariate Gaussians to the PCA-projected data. Each Gaussian is
     one "regime". Unlike K-means (which forces spherical clusters), GMM
     allows elliptical shapes and returns *soft* assignments — a probability
     that each cycle belongs to each regime.

     Model selection: we fit GMMs for K = 2..6 and pick the K that minimises
     BIC (Bayesian Information Criterion). BIC penalises complexity, so it
     balances fit quality against overfitting.

Typical regimes found on the NASA dataset
-----------------------------------------
  · Early life   — high voltage, low fade rate, many cycles remaining
  · Mid life     — gradual voltage drop, moderate temperature rise
  · Late life    — low voltage, accelerating fade, near EOL
  · High-thermal — elevated temperature cycles (often mid-life, warmer days)

These regimes are data-driven, not hand-labelled.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler


# ── Default clustering features ───────────────────────────────────────────────
# Exclude derived targets (soh, rul_*) and raw identifiers.
# Include capacity_fade_rate — it's the most direct degradation signal.

DEFAULT_FEATURES = [
    "discharge_num",
    "mean_discharge_voltage",
    "min_discharge_voltage",
    "mean_temperature",
    "max_temperature",
    "discharge_duration",
    "ambient_temp",
    "capacity_fade_rate",
]

FEATURE_LABELS = {
    "discharge_num":           "Cycle #",
    "mean_discharge_voltage":  "Mean voltage (V)",
    "min_discharge_voltage":   "Min voltage (V)",
    "mean_temperature":        "Mean temp (°C)",
    "max_temperature":         "Max temp (°C)",
    "discharge_duration":      "Duration (s)",
    "ambient_temp":            "Ambient temp (°C)",
    "capacity_fade_rate":      "Capacity fade rate (Ah)",
}


# ── Output dataclass ──────────────────────────────────────────────────────────

@dataclass
class RegimeResult:
    """All outputs from fit_regimes()."""
    df_out: pd.DataFrame          # original df + 'pc1','pc2','regime','regime_prob'
    pca: PCA                      # fitted PCA object
    gmm: GaussianMixture          # fitted GMM object
    scaler: StandardScaler        # fitted scaler
    feature_cols: list[str]       # features used
    n_clusters: int               # number of regimes
    explained_variance: np.ndarray  # per-component explained variance ratio
    loadings: pd.DataFrame        # PC loadings (features × components)
    bic_scores: dict[int, float]  # BIC for each K tried
    cluster_profiles: pd.DataFrame  # mean standardised feature per regime


# ── Core fitting function ─────────────────────────────────────────────────────

def fit_regimes(
    df: pd.DataFrame,
    feature_cols: list[str] | None = None,
    n_clusters: int | None = None,
    n_pca_components: int = 2,
    random_state: int = 42,
) -> RegimeResult:
    """
    Fit PCA + GMM on the discharge-cycle feature matrix.

    Parameters
    ----------
    df             : full battery features DataFrame (output of build_dataset)
    feature_cols   : features to use; defaults to DEFAULT_FEATURES
    n_clusters     : number of GMM components; if None, auto-selected via BIC
    n_pca_components : PCA dimensions to retain (2 for visualisation)
    random_state   : reproducibility seed

    Returns
    -------
    RegimeResult
    """
    if feature_cols is None:
        feature_cols = [f for f in DEFAULT_FEATURES if f in df.columns]

    # ── 1. Scale ─────────────────────────────────────────────────────────────
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df[feature_cols].dropna())
    df_clean = df[feature_cols].dropna().copy()
    idx_clean = df_clean.index

    # ── 2. PCA ───────────────────────────────────────────────────────────────
    pca = PCA(n_components=n_pca_components, random_state=random_state)
    X_pca = pca.fit_transform(X_scaled)

    loadings = pd.DataFrame(
        pca.components_.T,
        index=feature_cols,
        columns=[f"PC{i+1}" for i in range(n_pca_components)],
    )

    # ── 3. BIC model selection ────────────────────────────────────────────────
    bic_scores: dict[int, float] = {}
    for k in range(2, 7):
        gmm_k = GaussianMixture(
            n_components=k, covariance_type="full",
            random_state=random_state, n_init=3,
        )
        gmm_k.fit(X_pca)
        bic_scores[k] = gmm_k.bic(X_pca)

    best_k = min(bic_scores, key=bic_scores.get)
    chosen_k = n_clusters if n_clusters is not None else best_k

    # ── 4. Final GMM ──────────────────────────────────────────────────────────
    gmm = GaussianMixture(
        n_components=chosen_k, covariance_type="full",
        random_state=random_state, n_init=5,
    )
    gmm.fit(X_pca)
    labels = gmm.predict(X_pca)
    probs  = gmm.predict_proba(X_pca).max(axis=1)  # confidence of assignment

    # ── 5. Re-label clusters by PC1 order (low → high degradation) ───────────
    # Sort cluster centres by PC1 so regime 0 = "best health", regime K-1 = "worst"
    centres_pc1 = gmm.means_[:, 0]
    order       = np.argsort(centres_pc1)
    remap       = {old: new for new, old in enumerate(order)}
    labels      = np.array([remap[l] for l in labels])

    # ── 6. Assemble output DataFrame ─────────────────────────────────────────
    df_out = df.loc[idx_clean].copy()
    df_out["pc1"]         = X_pca[:, 0]
    df_out["pc2"]         = X_pca[:, 1]
    df_out["regime"]      = labels
    df_out["regime_prob"] = probs

    # ── 7. Cluster profiles (mean standardised values per regime) ─────────────
    df_out["_regime"] = labels
    profiles = (
        df_out.groupby("_regime")[feature_cols].mean()
        .rename(index={i: f"Regime {i}" for i in range(chosen_k)})
    )
    # Standardise for heatmap display
    cluster_profiles = (profiles - profiles.mean()) / (profiles.std() + 1e-9)
    df_out.drop(columns=["_regime"], inplace=True)

    return RegimeResult(
        df_out=df_out,
        pca=pca,
        gmm=gmm,
        scaler=scaler,
        feature_cols=feature_cols,
        n_clusters=chosen_k,
        explained_variance=pca.explained_variance_ratio_,
        loadings=loadings,
        bic_scores=bic_scores,
        cluster_profiles=cluster_profiles,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def regime_summary(result: RegimeResult) -> pd.DataFrame:
    """
    Summary table: for each regime, count cycles and mean SOH.
    Useful for the dashboard table view.
    """
    df = result.df_out
    rows = []
    for r in sorted(df["regime"].unique()):
        sub = df[df["regime"] == r]
        rows.append({
            "Regime":      f"Regime {r}",
            "Cycles":      len(sub),
            "Mean SOH":    f"{sub['soh'].mean():.1%}" if "soh" in sub else "—",
            "Mean voltage (V)": f"{sub['mean_discharge_voltage'].mean():.3f}"
                if "mean_discharge_voltage" in sub else "—",
            "Batteries":   ", ".join(sorted(sub["battery_id"].unique()))
                if "battery_id" in sub else "—",
        })
    return pd.DataFrame(rows)
