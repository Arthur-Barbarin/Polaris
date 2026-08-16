import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gnss.measurements import nominal, single_fault, MeasurementParams
from gnss.raim import (
    ls_solve, detect, exclude, protection_level, horizontal_slopes, RaimParams,
)

MP = MeasurementParams()


def test_ls_recovers_zero_state_on_clean_data():
    rng = np.random.default_rng(0)
    s = nominal(rng, MeasurementParams(sigma_ura=0.0))  # noise-free
    sol = ls_solve(s.H, s.z)
    assert np.allclose(sol.dx, 0.0, atol=1e-6)
    assert sol.sse < 1e-9


def test_clean_data_is_not_detected():
    rng = np.random.default_rng(1)
    fa = sum(detect(nominal(rng, MP), RaimParams()).detected for _ in range(500))
    assert fa < 15   # ~Pfa=1e-3 over 500 -> essentially none


def test_large_fault_is_detected_and_excluded():
    rng = np.random.default_rng(2)
    hits = correct = 0
    for _ in range(200):
        s = single_fault(rng, MP, bias_range=(100.0, 200.0))
        ex = exclude(s, RaimParams())
        if ex.detected:
            hits += 1
            if ex.correct:
                correct += 1
    assert hits > 190              # nearly always detected
    assert correct > 0.9 * hits    # and the right SV is removed


def test_exclusion_reduces_position_error():
    rng = np.random.default_rng(3)
    s = single_fault(rng, MP, bias_range=(150.0, 150.0))
    ex = exclude(s, RaimParams())
    assert ex.detected and ex.sol_after is not None
    before = np.hypot(*ex.sol_before.horizontal)
    after = np.hypot(*ex.sol_after.horizontal)
    assert after < before


def test_protection_level_available_for_good_geometry():
    rng = np.random.default_rng(4)
    s = nominal(rng, MP)
    pl = protection_level(s.H, s.sigma, RaimParams(hal=200.0))
    assert pl.hpl > 0
    assert pl.slope_max > 0
    assert pl.available   # 8-11 sats, sigma 5 m -> HPL well under 200 m


def test_slopes_are_finite_and_positive():
    rng = np.random.default_rng(5)
    s = nominal(rng, MP)
    slopes = horizontal_slopes(s.H)
    assert np.all(np.isfinite(slopes))
    assert np.all(slopes > 0)
