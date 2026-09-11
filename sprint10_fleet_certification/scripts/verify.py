"""Reproduce every headline number in the sprint 10 README.

Run:
    python scripts/verify.py

The script exits non-zero if any headline number falls outside its
expected range against the checked-in sprint 7-9 artefacts.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from polaris_fc import build_evidence, run_summary                # noqa: E402
from polaris_fc.requirements import Subsystem                     # noqa: E402


def _check(label: str, value, ok: bool) -> bool:
    tick = "✓" if ok else "✗"
    print(f"  {tick} {label}: {value}")
    return ok


def main() -> int:
    repo = HERE.parents[1]
    res = build_evidence(repo)
    summary = run_summary(res)

    print("=== Fleet Certification Console — verification ===")
    print(f"repo: {repo}")
    print(f"catalog: v{summary['catalog_version']}")
    print(f"fleet:   {summary['fleet_status']}")
    print()

    ok_all = True

    # Manifest sanity — we expect the three subsystems' primary artefacts
    # to be present in a clean checkout.
    print("manifest present:")
    expected_present = {
        ("BATTERY_PACK", "estimator_benchmark"),
        ("FIXED_WING_UAV", "campaign"),
        ("LANDING_MULTIROTOR", "campaign"),
    }
    present = {(r.subsystem, r.role) for r in res.manifest if r.exists}
    ok_all &= _check("all three primary artefacts present",
                     sorted(present & expected_present),
                     expected_present.issubset(present))

    # Total requirements count.
    ok_all &= _check("requirements catalog size",
                     summary["requirements_total"],
                     summary["requirements_total"] >= 10)

    # Battery — the EKF must beat coulomb counting in every condition it
    # exists to handle. Worst case, not mean: see FC-BAT-002's rationale.
    bat = [r for r in res.all_results() if r.requirement.id == "FC-BAT-002"]
    if bat:
        r = bat[0]
        v = r.aggregated_value
        ok_all &= _check("FC-BAT-002 worst-case EKF advantage where required",
                         f"{v:.1f}% (>={r.requirement.bound:.0f})", r.passed)

    # Battery — FC-BAT-005 is a KNOWN, TRACKED FINDING and is expected to
    # fail: under a pure shunt bias with a correct seed the EKF is worse than
    # the counter. The headline check is that it fails as a non-blocking
    # finding, not that it passes.
    nw = [r for r in res.all_results() if r.requirement.id == "FC-BAT-005"]
    if nw:
        r = nw[0]
        ok_all &= _check("FC-BAT-005 known finding, non-blocking",
                         f"worst {r.aggregated_value:.1f}% "
                         f"({'FAIL as expected' if not r.passed else 'PASSES - review'})",
                         not r.blocking)

    # Landing — nominal touchdown must land within pad radius (0.5 m) on
    # every seed of the sprint-9 nominal scenario.
    ldg = [r for r in res.all_results()
           if r.requirement.id == "FC-LDG-001"]
    if ldg:
        r = ldg[0]
        ok_all &= _check("FC-LDG-001 nominal touchdown worst-case",
                         f"{r.aggregated_value} m (<=0.5)",
                         r.passed)

    # Landing — unsafe finals must abort. This one has to pass or the whole
    # console's safety story is wrong.
    unsafe = [r for r in res.all_results() if r.requirement.id == "FC-LDG-003"]
    if unsafe:
        ok_all &= _check("FC-LDG-003 unsafe finals go around", unsafe[0].status,
                         unsafe[0].passed)

    # UAV — nominal mission passes.
    nom = [r for r in res.all_results() if r.requirement.id == "FC-UAV-001"]
    if nom:
        ok_all &= _check("FC-UAV-001 nominal mission pass fraction",
                         nom[0].aggregated_value, nom[0].passed)

    print()
    print("PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
