import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gnss.chi2 import chi2_cdf, chi2_ppf, ncx2_cdf, ncx2_pbias


def test_chi2_quantiles_match_tables():
    assert abs(chi2_ppf(0.95, 1) - 3.8415) < 2e-3
    assert abs(chi2_ppf(0.95, 2) - 5.9915) < 2e-3
    assert abs(chi2_ppf(0.99, 4) - 13.2767) < 2e-3
    assert abs(chi2_ppf(0.95, 6) - 12.5916) < 2e-3


def test_chi2_cdf_inverts_ppf():
    for k in (1, 3, 5, 8):
        for p in (0.5, 0.9, 0.99):
            x = chi2_ppf(p, k)
            assert abs(chi2_cdf(x, k) - p) < 1e-3


def test_ncx2_reduces_to_central_at_zero():
    assert abs(ncx2_cdf(10.0, 4, 0.0) - chi2_cdf(10.0, 4)) < 1e-9


def test_ncx2_cdf_decreases_with_noncentrality():
    a = ncx2_cdf(15.0, 4, 0.0)
    b = ncx2_cdf(15.0, 4, 8.0)
    c = ncx2_cdf(15.0, 4, 20.0)
    assert a > b > c


def test_pbias_is_positive_and_reasonable():
    thr = chi2_ppf(1 - 1e-3, 4)
    pb = ncx2_pbias(4, thr, 1e-3)
    assert 3.0 < pb < 10.0
