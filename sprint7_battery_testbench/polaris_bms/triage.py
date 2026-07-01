"""Failure triage / bucketization.

Two-stage pipeline used to auto-classify cycling anomalies into degradation
mode buckets, modelled on the Apple HSV JD's "triage / bucketize failures"
language.

  Stage 1 - dimensionality reduction (PCA) on the cycle-feature matrix.
  Stage 2 - Gaussian Mixture cluster assignment; each cluster is mapped to a
            named degradation mode by majority vote over labelled training
            cycles. New, unlabelled cycles get a soft cluster probability +
            top-hypothesis label.

Inputs are CycleRecord objects from polaris_bms.cycler.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from .cycler import CycleRecord


FEATURES = (
    "discharge_capacity_ah",
    "charge_capacity_ah",
    "coulombic_efficiency",
    "mean_discharge_voltage",
    "ir_drop_v",
    "rest_relaxation_v",
    "peak_charge_dvdq",
    "soh_pct",
    "d_soh_pct",
    "d_ir_drop_v",
    "d_mean_voltage_v",
)


def to_matrix(records: Iterable[CycleRecord]) -> Tuple[np.ndarray, List[str]]:
    X = np.array([[getattr(r, f) for f in FEATURES] for r in records], dtype=float)
    y = [r.fault for r in records]
    return X, y


@dataclass
class TriageResult:
    cycle: int
    predicted_mode: str
    cluster: int
    posterior: float


class FailureTriage:
    """PCA + Gaussian-Mixture triage with majority-vote cluster labelling."""

    def __init__(self, n_components: int = 4, n_clusters: int = 8, random_state: int = 0):
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=n_components)
        self.gmm = GaussianMixture(
            n_components=n_clusters, covariance_type="full",
            random_state=random_state, reg_covar=1e-4,
        )
        self.cluster_to_label: Dict[int, str] = {}

    def fit(self, records: List[CycleRecord]) -> "FailureTriage":
        X, y = to_matrix(records)
        Xs = self.scaler.fit_transform(X)
        Xp = self.pca.fit_transform(Xs)
        self.gmm.fit(Xp)
        labels = np.array(y)
        cluster_ids = self.gmm.predict(Xp)
        # Majority-vote per cluster.
        for k in range(self.gmm.n_components):
            mask = cluster_ids == k
            if not mask.any():
                self.cluster_to_label[k] = "Unknown"
                continue
            in_cluster = labels[mask]
            uniq, counts = np.unique(in_cluster, return_counts=True)
            self.cluster_to_label[k] = uniq[counts.argmax()] or "Healthy"
        return self

    def predict(self, records: List[CycleRecord]) -> List[TriageResult]:
        X, _ = to_matrix(records)
        Xs = self.scaler.transform(X)
        Xp = self.pca.transform(Xs)
        post = self.gmm.predict_proba(Xp)
        ids = post.argmax(axis=1)
        return [
            TriageResult(
                cycle=rec.cycle,
                predicted_mode=self.cluster_to_label.get(int(ids[i]), "Unknown"),
                cluster=int(ids[i]),
                posterior=float(post[i, ids[i]]),
            )
            for i, rec in enumerate(records)
        ]


def rul_projection(records: List[CycleRecord], eol_threshold_pct: float = 80.0) -> Optional[int]:
    """Linearise SoH(cycle) on the most recent third of the trace,
    project the cycle index at which SoH crosses the end-of-life threshold.
    """
    if len(records) < 10:
        return None
    cyc = np.array([r.cycle for r in records], dtype=float)
    soh = np.array([r.soh_pct for r in records], dtype=float)
    tail = max(10, len(records) // 3)
    a, b = np.polyfit(cyc[-tail:], soh[-tail:], 1)
    if a >= 0:           # SoH not declining - no projection possible
        return None
    eol_cycle = (eol_threshold_pct - b) / a
    if eol_cycle < cyc[-1]:
        return int(cyc[-1])
    return int(round(eol_cycle))
