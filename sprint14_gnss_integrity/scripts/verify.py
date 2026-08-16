"""Reproduce every headline number in the Sprint 14 README.

Run:
    python scripts/verify.py

Runs the deterministic N=2000, seed-14 threat campaign and asserts each
headline figure, plus the statistical-helper quantiles the RAIM thresholds are
built on. No network, no SciPy — everything is seeded geometry and a
hand-rolled incomplete-gamma. Exits non-zero on any drift.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from gnss import run_campaign                                        # noqa: E402
from gnss.chi2 import chi2_ppf, ncx2_cdf                            # noqa: E402

N, SEED = 2000, 14


def _check(label: str, value, ok: bool) -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: {value}")
    return ok


def main() -> int:
    print("=== GNSS Integrity Monitor — verification ===")
    ok = True

    # --- statistical helper pinned to published quantiles --------------------
    print("\nchi-square helper:")
    ok &= _check("chi2_ppf(0.95, 1) = 3.8415", f"{chi2_ppf(0.95, 1):.4f}",
                 abs(chi2_ppf(0.95, 1) - 3.8415) < 2e-3)
    ok &= _check("chi2_ppf(0.99, 4) = 13.277", f"{chi2_ppf(0.99, 4):.3f}",
                 abs(chi2_ppf(0.99, 4) - 13.2767) < 2e-3)
    ok &= _check("ncx2_cdf reduces to chi2 at lam=0", f"{ncx2_cdf(13.2767, 4, 0.0):.3f}",
                 abs(ncx2_cdf(13.2767, 4, 0.0) - 0.99) < 2e-3)

    r = run_campaign(N, seed=SEED)

    # --- nominal -------------------------------------------------------------
    print(f"\nnominal (N={N}, seed {SEED}):")
    ok &= _check("false-alarm rate near Pfa=1e-3", f"{r.fa_rate_full:.4f}",
                 r.fa_rate_full < 6e-3)
    ok &= _check("availability > 0.98", f"{r.availability:.3f}", r.availability > 0.98)

    # --- single fault --------------------------------------------------------
    print("\nsingle fault:")
    ok &= _check("detection rate > 0.95", f"{r.sf_detect_rate:.3f}", r.sf_detect_rate > 0.95)
    ok &= _check("correct-exclusion rate > 0.97", f"{r.sf_exclude_correct_rate:.3f}",
                 r.sf_exclude_correct_rate > 0.97)
    ok &= _check("exclusion reduces error", f"{r.sf_err_before:.1f} -> {r.sf_err_after:.1f} m",
                 r.sf_err_after < r.sf_err_before)

    # --- spoof (headline) ----------------------------------------------------
    print("\nspoof (headline):")
    ok &= _check("RAIM-only detection < 2%", f"{r.spoof_detect_raim:.3f}",
                 r.spoof_detect_raim < 0.02)
    ok &= _check("full-monitor detection = 1.000", f"{r.spoof_detect_full:.3f}",
                 r.spoof_detect_full == 1.0)
    ok &= _check("HMI: RAIM-only had events", r.spoof_hmi_raim, r.spoof_hmi_raim >= 10)
    ok &= _check("HMI: full monitor = 0", r.spoof_hmi_full, r.spoof_hmi_full == 0)

    # --- jamming -------------------------------------------------------------
    print("\njamming:")
    ok &= _check("detection rate = 1.000", f"{r.jam_detect_rate:.3f}",
                 r.jam_detect_rate == 1.0)

    # --- reproducibility -----------------------------------------------------
    print("\nreproducibility:")
    r2 = run_campaign(N, seed=SEED)
    ok &= _check("campaign stable across runs",
                 (r2.spoof_hmi_raim, r2.sf_detect_rate),
                 (r2.spoof_hmi_raim, r2.sf_detect_rate) == (r.spoof_hmi_raim, r.sf_detect_rate))

    print("\n" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
