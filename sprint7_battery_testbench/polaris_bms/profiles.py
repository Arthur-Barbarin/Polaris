"""Test profiles - waveforms applied to the cell during evaluation tests.

Each profile is a generator of (time_s, current_setpoint_a) tuples.
"""
from __future__ import annotations

from typing import Iterator, Tuple


def cc_discharge(current_a: float, duration_s: float, dt_s: float = 1.0) -> Iterator[Tuple[float, float]]:
    t = 0.0
    while t < duration_s:
        yield t, float(current_a)
        t += dt_s


def cccv_charge(
    current_a: float,
    v_target: float,
    duration_s: float,
    dt_s: float = 1.0,
    taper_threshold: float = 0.05,
) -> Iterator[Tuple[float, float]]:
    """Constant current then taper - caller checks voltage between steps."""
    t = 0.0
    while t < duration_s:
        yield t, -abs(float(current_a))
        t += dt_s


def hppc_pulse_train(
    soc_breakpoints,
    pulse_a: float = 3.2,
    pulse_s: float = 10.0,
    rest_s: float = 40.0,
    inter_break_discharge_s: float = 60.0,
    dt_s: float = 1.0,
):
    """HPPC = Hybrid Pulse Power Characterisation.

    Per SOC breakpoint, apply: discharge pulse -> rest -> charge pulse -> rest.
    Caller drives SOC down between breakpoints by `inter_break_discharge_s` at
    `pulse_a`. We yield only the pulse-train portion; the orchestrator handles
    the SOC stepping. This separation matches how lab test plans are structured.
    """
    t = 0.0
    for _ in soc_breakpoints:
        # Discharge pulse
        end = t + pulse_s
        while t < end:
            yield t, float(pulse_a)
            t += dt_s
        # Rest
        end = t + rest_s
        while t < end:
            yield t, 0.0
            t += dt_s
        # Charge pulse
        end = t + pulse_s
        while t < end:
            yield t, -float(pulse_a)
            t += dt_s
        # Rest
        end = t + rest_s
        while t < end:
            yield t, 0.0
            t += dt_s
