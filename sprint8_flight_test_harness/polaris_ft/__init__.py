"""Polaris Sprint 8 — Autonomous UAV Flight-Test Validation Harness.

A closed-loop fixed-wing simulator (reduced-order dynamics + cascaded autopilot
+ navigation EKF) driven through fault-injection campaigns, graded by a
versioned flight-test-card engine, with PCA+GMM anomaly triage over the runs.

All telemetry is SYNTHETIC (simulator output), not captured from real flight
hardware.
"""
from .vehicle import Airframe, VehicleState, ControlInput, Wind, Actuator, step_rk4
from .mission import Mission, Waypoint, Geofence, default_mission
from .controller import Autopilot, Gains
from .estimator import NavEKF, EkfState
from .signals import SensorConfig, SensorSuite, Measurement
from .faults import Scenario, ALL_SCENARIOS
from .simulator import simulate, FlightLog
from .testcards import (
    compute_metrics, grade, FlightMetrics, TestCardReport,
    DEFAULT_CRITERIA, CARD_VERSION,
)
from .triage import FlightTriage, TriageResult

__all__ = [
    "Airframe", "VehicleState", "ControlInput", "Wind", "Actuator", "step_rk4",
    "Mission", "Waypoint", "Geofence", "default_mission",
    "Autopilot", "Gains", "NavEKF", "EkfState",
    "SensorConfig", "SensorSuite", "Measurement",
    "Scenario", "ALL_SCENARIOS", "simulate", "FlightLog",
    "compute_metrics", "grade", "FlightMetrics", "TestCardReport",
    "DEFAULT_CRITERIA", "CARD_VERSION",
    "FlightTriage", "TriageResult",
]
