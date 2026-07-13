"""Touchdown dispersion statistics and approach anomaly triage.

`cep()` turns a set of touchdown points into the circular-error-probable
metrics flight-test uses to characterise landing accuracy (CEP50 / CEP95) plus
a 1-sigma covariance ellipse.

`LandingTriage` reuses the Polaris PCA+GMM pattern (Sprints 3/7/8) to auto-bucket
approaches into nominal / fault modes from their telemetry-derived features.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from .testcards import LandingMetrics

# max_sink was dropped: it is schedule-limited to ~2.88 m/s on every run
# (std ~0.01), so it carried no discriminative signal for triage.
FEATURES = (
    "max_lateral_final",
    "vision_avail_final",
    "nav_err_final",
    "descent_time",
    "gps_vision_disagree",
    "vision_avail_high",
    "go_around_flag",
)


@dataclass
class CEP:
    n: int
    cep50: float          # about the sample mean -> PRECISION
    cep95: float
    mean_x: float
    mean_y: float
    bias: float           # |mean touchdown offset from the pad| -> systematic error
    cep50_pad: float      # about the pad origin -> ACCURACY (bias + scatter)
    cep95_pad: float
    ellipse_a: float      # 1-sigma semi-major [m]
    ellipse_b: float      # 1-sigma semi-minor [m]
    ellipse_angle: float  # [rad]


def cep(points: np.ndarray) -> CEP:
    """points: (N,2) touchdown offsets from the pad [m] (landed runs only).

    Reports BOTH precision (CEP about the sample mean) and accuracy (CEP about
    the pad origin) plus the mean bias, so a steady-wind touchdown offset is
    not hidden by measuring scatter about a displaced mean.
    """
    pts = np.asarray(points, dtype=float)
    pts = pts[~np.isnan(pts).any(axis=1)]
    if len(pts) == 0:
        return CEP(0, *([np.nan] * 9))
    mean = pts.mean(axis=0)
    r_mean = np.hypot(pts[:, 0] - mean[0], pts[:, 1] - mean[1])
    r_pad = np.hypot(pts[:, 0], pts[:, 1])
    cep50 = float(np.median(r_mean))
    cep95 = float(np.percentile(r_mean, 95))
    cep50_pad = float(np.median(r_pad))
    cep95_pad = float(np.percentile(r_pad, 95))
    bias = float(np.hypot(mean[0], mean[1]))
    if len(pts) >= 2:
        cov = np.cov(pts.T)
        w, V = np.linalg.eigh(cov)
        w = np.clip(w, 0, None)
        order = np.argsort(w)[::-1]
        a, b = np.sqrt(w[order[0]]), np.sqrt(w[order[1]])
        angle = float(np.arctan2(V[1, order[0]], V[0, order[0]]))
    else:
        a = b = angle = 0.0
    return CEP(len(pts), cep50, cep95, float(mean[0]), float(mean[1]),
              bias, cep50_pad, cep95_pad, float(a), float(b), angle)


def _feature_row(m: LandingMetrics) -> List[float]:
    nav = m.nav_err_final if not np.isnan(m.nav_err_final) else 1.0
    return [m.max_lateral_final, m.vision_avail_final, nav,
            m.descent_time, m.gps_vision_disagree,
            m.vision_avail_high, 1.0 if m.go_around else 0.0]


def to_matrix(metrics: List[LandingMetrics]) -> Tuple[np.ndarray, List[str]]:
    X = np.array([_feature_row(m) for m in metrics], dtype=float)
    y = [m.label for m in metrics]
    return X, y


@dataclass
class TriageResult:
    label: str
    predicted_mode: str
    cluster: int
    posterior: float


class LandingTriage:
    def __init__(self, n_components: int = 4, n_clusters: int = 10, random_state: int = 0):
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=n_components, random_state=random_state)
        self.gmm = GaussianMixture(n_components=n_clusters, covariance_type="full",
                                   random_state=random_state, n_init=3)
        self.n_clusters = n_clusters
        self.cluster_to_mode: Dict[int, str] = {}

    def fit(self, metrics: List[LandingMetrics]) -> "LandingTriage":
        X, y = to_matrix(metrics)
        Z = self.pca.fit_transform(self.scaler.fit_transform(X))
        clusters = self.gmm.fit_predict(Z)
        for c in range(self.n_clusters):
            members = [y[i] for i in range(len(y)) if clusters[i] == c]
            self.cluster_to_mode[c] = (max(set(members), key=members.count)
                                       if members else "UNKNOWN")
        return self

    def predict(self, metrics: List[LandingMetrics]) -> List[TriageResult]:
        X, y = to_matrix(metrics)
        Z = self.pca.transform(self.scaler.transform(X))
        clusters = self.gmm.predict(Z)
        post = self.gmm.predict_proba(Z)
        return [TriageResult(y[i], self.cluster_to_mode.get(int(clusters[i]), "UNKNOWN"),
                             int(clusters[i]), float(post[i, int(clusters[i])]))
                for i in range(len(metrics))]

    def transform_2d(self, metrics: List[LandingMetrics]) -> np.ndarray:
        X, _ = to_matrix(metrics)
        return self.pca.transform(self.scaler.transform(X))[:, :2]

    @staticmethod
    def accuracy(results: List[TriageResult]) -> float:
        if not results:
            return 0.0
        return sum(r.predicted_mode == r.label for r in results) / len(results)
