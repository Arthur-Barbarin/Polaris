"""Chi-square and non-central chi-square, dependency-light.

RAIM needs three statistical quantities and nothing heavier:

* a **detection threshold** — the chi-square quantile for a false-alarm
  probability (central chi-square inverse CDF),
* a **non-centrality parameter** (``pbias``) — how large a bias must be, in
  sigma units, before it is caught with the required missed-detection
  probability (non-central chi-square inverse),
* CDF evaluations to score empirical rates.

Pulling in SciPy for this would be overkill and a deployment liability, so the
regularized lower incomplete gamma function is implemented directly (series +
continued fraction, the standard Numerical-Recipes split) and everything else
is built on it. The unit tests pin the outputs to published quantiles.
"""
from __future__ import annotations

import math

_MAXIT = 300
_EPS = 3.0e-12


def _gser(a: float, x: float) -> float:
    """Regularized lower incomplete gamma P(a, x) by series (good for x < a+1)."""
    if x <= 0.0:
        return 0.0
    ap = a
    total = 1.0 / a
    delta = total
    for _ in range(_MAXIT):
        ap += 1.0
        delta *= x / ap
        total += delta
        if abs(delta) < abs(total) * _EPS:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gcf(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x) by continued fraction (x >= a+1)."""
    tiny = 1.0e-30
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, _MAXIT):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def gammainc_lower_reg(a: float, x: float) -> float:
    """Regularized lower incomplete gamma P(a, x) = gamma(a, x) / Gamma(a)."""
    if x < 0.0 or a <= 0.0:
        raise ValueError("gammainc_lower_reg requires a > 0 and x >= 0")
    if x == 0.0:
        return 0.0
    if x < a + 1.0:
        return _gser(a, x)
    return 1.0 - _gcf(a, x)


def chi2_cdf(x: float, k: int) -> float:
    """CDF of a chi-square with ``k`` degrees of freedom."""
    if x <= 0.0:
        return 0.0
    return gammainc_lower_reg(k / 2.0, x / 2.0)


def chi2_sf(x: float, k: int) -> float:
    """Survival function 1 - CDF."""
    return 1.0 - chi2_cdf(x, k)


def chi2_ppf(p: float, k: int) -> float:
    """Inverse CDF (quantile) of a chi-square with ``k`` dof, by bisection."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0, 1)")
    lo, hi = 0.0, 2.0
    while chi2_cdf(hi, k) < p:
        hi *= 2.0
        if hi > 1e9:
            break
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if chi2_cdf(mid, k) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def ncx2_cdf(x: float, k: int, lam: float) -> float:
    """CDF of a non-central chi-square, dof ``k``, non-centrality ``lam``.

    Poisson-weighted mixture of central chi-squares:
        F(x; k, lam) = sum_j e^{-lam/2} (lam/2)^j / j!  *  chi2_cdf(x; k + 2j)
    """
    if lam <= 0.0:
        return chi2_cdf(x, k)
    if x <= 0.0:
        return 0.0
    half = lam / 2.0
    total = 0.0
    log_w = -half  # log Poisson weight for j=0
    for j in range(0, _MAXIT):
        if j > 0:
            log_w += math.log(half) - math.log(j)
        w = math.exp(log_w)
        total += w * chi2_cdf(x, k + 2 * j)
        if j > half and w < _EPS:
            break
    return total


def ncx2_pbias(k: int, threshold: float, pmd: float) -> float:
    """Bias size (in sigma units) caught at the missed-detection prob ``pmd``.

    Solves ``ncx2_cdf(threshold; k, lam) = pmd`` for the non-centrality ``lam``
    and returns ``sqrt(lam)`` — the classic RAIM ``pbias`` used to size the
    protection level.
    """
    lo, hi = 0.0, 1.0
    while ncx2_cdf(threshold, k, hi) > pmd:
        hi *= 2.0
        if hi > 1e7:
            break
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        # CDF is decreasing in lam, so flip the comparison
        if ncx2_cdf(threshold, k, mid) > pmd:
            lo = mid
        else:
            hi = mid
    return math.sqrt(0.5 * (lo + hi))
