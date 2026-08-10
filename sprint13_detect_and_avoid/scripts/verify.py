"""Reproduce every headline number in the Sprint 13 README.

Run:
    python scripts/verify.py

Runs the deterministic Monte-Carlo campaign (N=2000, seed 13) both nominal and
degraded-surveillance, and asserts each headline figure. No network, no model
weights — everything is seeded geometry, so the numbers are byte-for-byte
reproducible. Exits non-zero on any drift.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from daa import encounter_set, run_campaign            # noqa: E402
from daa.metrics import SimParams                       # noqa: E402
from daa.wellclear import DWC, NMAC, FT                 # noqa: E402

N, SEED, STRESS_RANGE = 2000, 13, 926.0  # 926 m = 0.5 NM


def _check(label: str, value, ok: bool) -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: {value}")
    return ok


def main() -> int:
    print("=== Detect-and-Avoid — verification ===")
    ok = True

    # --- Thresholds are the published DO-365 values --------------------------
    print("\nDO-365 Well Clear thresholds:")
    ok &= _check("DMOD = 4000 ft", f"{DWC.dmod:.1f} m", math.isclose(DWC.dmod, 4000 * FT))
    ok &= _check("ZTHR = 450 ft", f"{DWC.zthr:.2f} m", math.isclose(DWC.zthr, 450 * FT))
    ok &= _check("tau_mod = 35 s", DWC.taumod_thr, DWC.taumod_thr == 35.0)
    ok &= _check("NMAC = 500 ft x 100 ft",
                 f"{NMAC.horizontal:.1f} x {NMAC.vertical:.1f} m",
                 math.isclose(NMAC.horizontal, 500 * FT) and math.isclose(NMAC.vertical, 100 * FT))

    enc = encounter_set(N, seed=SEED)
    nominal = run_campaign(enc)
    stress = run_campaign(enc, sim=SimParams(surveillance_range=STRESS_RANGE))

    # --- Nominal: DAA eliminates NMAC ----------------------------------------
    print(f"\nnominal campaign (N={N}, seed {SEED}, perfect surveillance):")
    ok &= _check("baseline NMACs", nominal.nmac_unequipped, nominal.nmac_unequipped == 31)
    ok &= _check("equipped NMACs", nominal.nmac_equipped, nominal.nmac_equipped == 0)
    ok &= _check("risk ratio", f"{nominal.risk_ratio:.3f}", nominal.risk_ratio == 0.0)
    ok &= _check("all baseline collisions resolved",
                 f"{nominal.resolved_nmacs}/{nominal.resolved_nmacs + nominal.unresolved_nmacs}",
                 nominal.resolved_nmacs == 31 and nominal.unresolved_nmacs == 0)
    ok &= _check("LoWC reduced",
                 f"{100*nominal.lowc_rate_unequipped:.1f}% -> {100*nominal.lowc_rate_equipped:.1f}%",
                 nominal.lowc_rate_equipped < nominal.lowc_rate_unequipped)
    ok &= _check("median alert lead > 45 s", f"{nominal.median_alert_lead:.1f} s",
                 nominal.median_alert_lead > 45.0)

    # --- Stress: degraded surveillance reintroduces quantified risk ----------
    print(f"\ndegraded campaign (sensor range {STRESS_RANGE:.0f} m = 0.5 NM):")
    ok &= _check("residual equipped NMACs", stress.nmac_equipped, stress.nmac_equipped == 10)
    ok &= _check("risk ratio in (0, 1)", f"{stress.risk_ratio:.3f}",
                 0.0 < stress.risk_ratio < 1.0)
    ok &= _check("some collisions unresolved", stress.unresolved_nmacs,
                 stress.unresolved_nmacs == 10)
    ok &= _check("alert lead collapses vs nominal",
                 f"{stress.median_alert_lead:.1f} s < {nominal.median_alert_lead:.1f} s",
                 stress.median_alert_lead < nominal.median_alert_lead)

    # --- Reproducibility -----------------------------------------------------
    print("\nreproducibility:")
    again = run_campaign(enc)
    ok &= _check("campaign counts stable across runs",
                 (again.nmac_unequipped, again.nmac_equipped),
                 (again.nmac_unequipped, again.nmac_equipped)
                 == (nominal.nmac_unequipped, nominal.nmac_equipped))

    print("\n" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
