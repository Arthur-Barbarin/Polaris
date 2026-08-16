import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gnss.constellation import (
    Satellite, geometry_matrix, dop, cofactor, random_constellation,
)


def test_los_zenith_points_straight_up():
    s = Satellite(az=1.2, el=math.pi / 2)
    e, n, u = s.los
    assert abs(e) < 1e-9 and abs(n) < 1e-9 and abs(u - 1.0) < 1e-9


def test_geometry_matrix_shape_and_clock_column():
    sats = [Satellite(az=a, el=0.5) for a in (0.0, 1.5, 3.0, 4.5)]
    H = geometry_matrix(sats)
    assert H.shape == (4, 4)
    assert np.allclose(H[:, 3], 1.0)   # clock column is all ones


def test_dop_improves_with_more_satellites():
    rng = np.random.default_rng(0)
    d4 = dop(geometry_matrix(random_constellation(rng, 4)))["GDOP"]
    d10 = dop(geometry_matrix(random_constellation(rng, 10)))["GDOP"]
    assert d10 < d4   # more satellites -> lower dilution of precision


def test_cofactor_is_symmetric_positive():
    rng = np.random.default_rng(1)
    Q = cofactor(geometry_matrix(random_constellation(rng, 8)))
    assert np.allclose(Q, Q.T)
    assert np.all(np.diag(Q) > 0)


def test_constellation_respects_elevation_mask():
    rng = np.random.default_rng(2)
    sats = random_constellation(rng, 20, mask_deg=10.0)
    assert all(s.el >= math.radians(10.0) - 1e-9 for s in sats)
