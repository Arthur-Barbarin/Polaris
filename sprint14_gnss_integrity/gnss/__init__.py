"""GNSS Integrity Monitor — RAIM fault detection/exclusion, protection levels,
and spoofing/jamming detection over a seeded Monte-Carlo threat field.

All geometry is linearized GNSS in a local ENU frame with published RAIM
statistics; every figure traces to a residual, a distance, or a count.
"""
from __future__ import annotations

from .constellation import (
    Satellite,
    geometry_matrix,
    dop,
    cofactor,
    random_constellation,
)
from .measurements import (
    MeasurementParams,
    Scenario,
    nominal,
    single_fault,
    spoof,
    jamming,
)
from .raim import (
    LSSolution,
    RaimParams,
    ls_solve,
    detect,
    exclude,
    protection_level,
    horizontal_slopes,
    detection_threshold,
)
from .spoofing import (
    SpoofParams,
    IntegrityStatus,
    screen,
    jamming_flag,
    cn0_spoof_flag,
    innovation_flag,
    innovation_mahalanobis,
)
from .metrics import (
    CampaignResult,
    run_campaign,
)

__all__ = [
    "Satellite", "geometry_matrix", "dop", "cofactor", "random_constellation",
    "MeasurementParams", "Scenario", "nominal", "single_fault", "spoof", "jamming",
    "LSSolution", "RaimParams", "ls_solve", "detect", "exclude", "protection_level",
    "horizontal_slopes", "detection_threshold",
    "SpoofParams", "IntegrityStatus", "screen", "jamming_flag", "cn0_spoof_flag",
    "innovation_flag", "innovation_mahalanobis",
    "CampaignResult", "run_campaign",
]
