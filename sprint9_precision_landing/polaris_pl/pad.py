"""Landing pad description.

The guidance frame is centred on the *expected* pad location (origin). The
*actual* pad may sit at a small offset (a survey error or a moved pad) — the
`offset_pad` fault exercises exactly this, and the camera sees the actual pad
while GPS is referenced to the expected one.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LandingPad:
    x: float = 0.0            # actual pad East position [m] (expected = 0)
    y: float = 0.0            # actual pad North position [m]
    marker_size_m: float = 0.5   # fiducial edge length [m] (documentation)
    touchdown_radius_m: float = 0.5  # acceptance radius for a good touchdown
