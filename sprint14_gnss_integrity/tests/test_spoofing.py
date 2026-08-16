import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gnss.measurements import nominal, spoof, jamming, MeasurementParams
from gnss.raim import detect, ls_solve, RaimParams
from gnss.spoofing import screen, jamming_flag, innovation_mahalanobis, SpoofParams

MP = MeasurementParams()
RP = RaimParams()


def test_coordinated_spoof_is_invisible_to_raim():
    rng = np.random.default_rng(0)
    raim_hits = 0
    for _ in range(300):
        s = spoof(rng, MP)
        if detect(s, RP).detected:
            raim_hits += 1
    assert raim_hits < 10   # residual RAIM is blind by construction


def test_full_monitor_catches_spoof():
    rng = np.random.default_rng(1)
    caught = 0
    for _ in range(300):
        s = spoof(rng, MP)
        if not screen(s, RP).trustworthy:
            caught += 1
    assert caught > 285     # C/N0 + innovation screen catches essentially all


def test_spoof_moves_the_solution():
    rng = np.random.default_rng(2)
    s = spoof(rng, MP, offset_range=(100.0, 100.0))
    err = np.hypot(*ls_solve(s.H, s.z).horizontal)
    assert err > 50.0       # the fix really is displaced


def test_nominal_is_trustworthy():
    rng = np.random.default_rng(3)
    trusted = sum(screen(nominal(rng, MP), RP).trustworthy for _ in range(300))
    assert trusted > 290    # almost never falsely rejected


def test_jamming_is_flagged():
    rng = np.random.default_rng(4)
    flagged = sum(jamming_flag(jamming(rng, MP), MP) for _ in range(200))
    assert flagged == 200


def test_innovation_large_under_spoof_small_under_nominal():
    rng = np.random.default_rng(5)
    dn = np.median([innovation_mahalanobis(nominal(rng, MP), RP) for _ in range(100)])
    ds = np.median([innovation_mahalanobis(spoof(rng, MP), RP) for _ in range(100)])
    assert ds > dn
