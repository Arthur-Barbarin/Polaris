"""Anomaly triage over flight-test runs (PCA + Gaussian Mixture).

Same two-stage pattern as the Sprint 7 battery-testbench triage, applied to
flight-log-level feature vectors instead of battery cycle features:

  Stage 1  StandardScaler -> PCA on the per-run metric matrix.
  Stage 2  Gaussian Mixture clustering; each cluster is mapped to a named
           anomaly mode by majority vote over labelled training runs.

Given many runs per scenario (varied by RNG seed), this learns to bucket an
unlabelled flight into NOMINAL / WIND_STEP / WIND_SHEAR / GPS_DROPOUT /
AIRSPEED_BIAS / AILERON_LOSS / ELEVATOR_LOSS from its telemetry signature.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from .testcards import FlightMetrics

FEATURES = (
    "cross_track_rms",
    "cross_track_max",
    "alt_hold_rms",
    "airspeed_hold_rms",
    "airspeed_mean_err",
    "throttle_sat_pct",
    "bank_sat_pct",
    "est_pos_rmse",
    "est_pos_max",
)


def to_matrix(metrics: List[FlightMetrics]) -> Tuple[np.ndarray, List[str]]:
    X = np.array([[getattr(m, f) for f in FEATURES] for m in metrics], dtype=float)
    y = [m.label for m in metrics]
    return X, y


@dataclass
class TriageResult:
    label: str
    predicted_mode: str
    cluster: int
    posterior: float


class FlightTriage:
    def __init__(self, n_components: int = 4, n_clusters: int = 8, random_state: int = 0):
        self.n_components = n_components
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=n_components, random_state=random_state)
        self.gmm = GaussianMixture(n_components=n_clusters,
                                   covariance_type="full",
                                   random_state=random_state, n_init=3)
        self.cluster_to_mode: Dict[int, str] = {}

    def fit(self, metrics: List[FlightMetrics]) -> "FlightTriage":
        X, y = to_matrix(metrics)
        Xs = self.scaler.fit_transform(X)
        Z = self.pca.fit_transform(Xs)
        clusters = self.gmm.fit_predict(Z)
        # Majority-vote label per cluster.
        for c in range(self.n_clusters):
            members = [y[i] for i in range(len(y)) if clusters[i] == c]
            if members:
                self.cluster_to_mode[c] = max(set(members), key=members.count)
            else:
                self.cluster_to_mode[c] = "UNKNOWN"
        return self

    def predict(self, metrics: List[FlightMetrics]) -> List[TriageResult]:
        X, y = to_matrix(metrics)
        Xs = self.scaler.transform(X)
        Z = self.pca.transform(Xs)
        clusters = self.gmm.predict(Z)
        post = self.gmm.predict_proba(Z)
        out: List[TriageResult] = []
        for i in range(len(metrics)):
            c = int(clusters[i])
            out.append(TriageResult(
                label=y[i],
                predicted_mode=self.cluster_to_mode.get(c, "UNKNOWN"),
                cluster=c,
                posterior=float(post[i, c]),
            ))
        return out

    def transform_2d(self, metrics: List[FlightMetrics]) -> np.ndarray:
        """First two PCA components, for dashboard scatter plots."""
        X, _ = to_matrix(metrics)
        Z = self.pca.transform(self.scaler.transform(X))
        return Z[:, :2]

    @staticmethod
    def accuracy(results: List[TriageResult]) -> float:
        if not results:
            return 0.0
        correct = sum(1 for r in results if r.predicted_mode == r.label)
        return correct / len(results)
