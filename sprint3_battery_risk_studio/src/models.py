"""
models.py
---------
Model definitions and serialization for the Polaris battery degradation pipeline.

We keep this simple: two models, clearly separated.

    LinearRegression  — baseline. Interpretable coefficients, fast to train.
                        Requires feature scaling (StandardScaler applied inside).

    RandomForestRegressor — main model. Handles non-linearity and feature
                        interactions without scaling. More accurate on this
                        dataset but requires SHAP for interpretation.

Both are wrapped as sklearn Pipelines so that the scaler (where needed) is
always bundled with the model — no risk of forgetting to scale at inference time.
"""

from __future__ import annotations

from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


# ── Model builders ────────────────────────────────────────────────────────────

def build_linear_regression() -> Pipeline:
    """
    Linear regression wrapped in a scaling pipeline.

    Why scale for linear regression?
    Linear regression is sensitive to feature magnitude — without scaling,
    a feature with large values (e.g. discharge_duration ~3000 s) would
    appear to have a tiny coefficient compared to a feature in [0, 1],
    making coefficients incomparable. StandardScaler fixes this.

    Returns
    -------
    sklearn.pipeline.Pipeline
    """
    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("model",  LinearRegression()),
        ]
    )


def build_random_forest(
    n_estimators: int = 300,
    max_depth: int | None = None,
    min_samples_leaf: int = 2,
    random_state: int = 42,
) -> RandomForestRegressor:
    """
    Random Forest regressor — the main model.

    Why no scaling here?
    Tree-based models split on feature thresholds, so the absolute scale of
    a feature does not affect the result. Scaling is unnecessary and would
    only add complexity.

    Hyperparameter notes
    --------------------
    n_estimators=300 : more trees = lower variance. 300 is a safe default
        for a dataset this size; diminishing returns above ~500.
    min_samples_leaf=2 : prevents single-sample leaves (overfitting).
        Relaxed from the default of 1 because the dataset is small (~600 rows).
    max_depth=None : let trees grow fully. We rely on the ensemble averaging
        to control variance rather than restricting depth.

    Returns
    -------
    RandomForestRegressor
    """
    return RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        random_state=random_state,
        n_jobs=-1,
    )


# ── Serialization ─────────────────────────────────────────────────────────────

def save_model(model, path: str | Path) -> None:
    """Save a fitted model (or pipeline) to disk with joblib."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    print(f"  Model saved → {path}")


def load_model(path: str | Path):
    """Load a model previously saved with save_model."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")
    return joblib.load(path)
