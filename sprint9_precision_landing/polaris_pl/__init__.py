"""Polaris Sprint 9 — Precision-Landing Validation Studio.

A closed-loop vision-guided precision-landing simulator: multirotor descent
dynamics + pinhole fiducial camera + GPS/vision fusion filter + gated descent
guidance with go-around logic, scored by landing test cards and characterised
by Monte-Carlo touchdown dispersion (CEP) and PCA+GMM approach triage.

All camera/GPS/telemetry are SYNTHETIC measurements (projected geometry), not
real image pixels or flight hardware.
"""
from .vehicle import Multirotor, VehicleState, AccelCommand, step_rk4, G
from .pad import LandingPad
from .camera import Camera, CameraConfig, VisionMeasurement
from .signals import SensorConfig, SensorSuite
from .estimator import LandingKF, KFState
from .guidance import LandingGuidance, GuidanceGains, Phase
from .faults import Scenario, ALL_SCENARIOS
from .simulator import simulate, ApproachLog, FINAL_APPROACH_Z
from .testcards import (
    compute_metrics, grade, LandingMetrics, LandingReport, CARD_VERSION,
    DEFAULT_CRITERIA,
)
from .dispersion import cep, CEP, LandingTriage, TriageResult

__all__ = [
    "Multirotor", "VehicleState", "AccelCommand", "step_rk4", "G",
    "LandingPad", "Camera", "CameraConfig", "VisionMeasurement",
    "SensorConfig", "SensorSuite", "LandingKF", "KFState",
    "LandingGuidance", "GuidanceGains", "Phase",
    "Scenario", "ALL_SCENARIOS", "simulate", "ApproachLog", "FINAL_APPROACH_Z",
    "compute_metrics", "grade", "LandingMetrics", "LandingReport",
    "CARD_VERSION", "DEFAULT_CRITERIA",
    "cep", "CEP", "LandingTriage", "TriageResult",
]
