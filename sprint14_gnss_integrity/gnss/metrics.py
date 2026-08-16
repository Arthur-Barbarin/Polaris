"""Campaign-level integrity metrics over a seeded threat field.

Four scenario families are each run ``n`` times and scored the way a GNSS
integrity requirement is written:

* **nominal** — false-alarm rate (RAIM-only and full screen) and availability
  (fraction with HPL < HAL);
* **single fault** — detection rate, correct-exclusion rate, and the horizontal
  position error before vs after exclusion;
* **spoof** — detection rate of residual RAIM *alone* versus the full screen,
  and the count of Hazardously Misleading Information events (position error
  beyond the alert limit while the system reports the fix as usable);
* **jamming** — detection rate from the C/N0 floor.

The headline is the spoof row: coordinated spoofing is, by construction, nearly
invisible to residual RAIM, so the value of the added C/N0 + innovation screen
is the collapse in HMI events — the integrity analogue of a risk ratio.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .measurements import (
    MeasurementParams,
    nominal as scn_nominal,
    single_fault as scn_single_fault,
    spoof as scn_spoof,
    jamming as scn_jamming,
)
from .raim import RaimParams, ls_solve, detect, exclude, protection_level
from .spoofing import SpoofParams, screen


def _horiz_err(sol) -> float:
    return float(np.hypot(sol.horizontal[0], sol.horizontal[1]))


@dataclass
class CampaignResult:
    n: int
    # nominal
    fa_rate_full: float
    fa_rate_raim: float
    availability: float
    median_hpl: float
    # single fault
    sf_detect_rate: float
    sf_exclude_correct_rate: float
    sf_err_before: float
    sf_err_after: float
    sf_hmi_raim: int
    # spoof
    spoof_detect_raim: float
    spoof_detect_full: float
    spoof_hmi_raim: int
    spoof_hmi_full: int
    # jamming
    jam_detect_rate: float
    params: dict = field(default_factory=dict)

    @property
    def spoof_hmi_ratio(self) -> float:
        if self.spoof_hmi_raim == 0:
            return float("nan")
        return self.spoof_hmi_full / self.spoof_hmi_raim


def run_campaign(
    n: int = 2000,
    seed: int = 14,
    mp: MeasurementParams = MeasurementParams(),
    rp: RaimParams = RaimParams(),
    sp: SpoofParams = SpoofParams(),
) -> CampaignResult:
    rng = np.random.default_rng(seed)

    # --- nominal ------------------------------------------------------------
    fa_full = fa_raim = avail = 0
    hpls: list[float] = []
    for _ in range(n):
        s = scn_nominal(rng, mp)
        st = screen(s, rp, sp, mp)
        if not st.trustworthy:
            fa_full += 1
        if st.raim_detected:
            fa_raim += 1
        pl = protection_level(s.H, s.sigma, rp)
        hpls.append(pl.hpl)
        if pl.available:
            avail += 1

    # --- single fault -------------------------------------------------------
    sf_det = sf_corr = sf_hmi = 0
    err_before: list[float] = []
    err_after: list[float] = []
    for _ in range(n):
        s = scn_single_fault(rng, mp)
        ex = exclude(s, rp)
        st = screen(s, rp, sp, mp)
        eb = _horiz_err(ex.sol_before)
        err_before.append(eb)
        if ex.detected:
            sf_det += 1
            if ex.correct:
                sf_corr += 1
            if ex.sol_after is not None:
                err_after.append(_horiz_err(ex.sol_after))
        # HMI: solution error beyond alert limit but nothing flagged it
        if eb > rp.hal and st.trustworthy:
            sf_hmi += 1

    # --- spoof --------------------------------------------------------------
    sp_raim = sp_full = sp_hmi_raim = sp_hmi_full = 0
    for _ in range(n):
        s = scn_spoof(rng, mp)
        st = screen(s, rp, sp, mp)
        err = _horiz_err(ls_solve(s.H, s.z))
        if st.raim_detected:
            sp_raim += 1
        if not st.trustworthy:
            sp_full += 1
        if err > rp.hal and not st.raim_detected:
            sp_hmi_raim += 1
        if err > rp.hal and st.trustworthy:
            sp_hmi_full += 1

    # --- jamming ------------------------------------------------------------
    jam_det = 0
    for _ in range(n):
        s = scn_jamming(rng, mp)
        st = screen(s, rp, sp, mp)
        if st.jam_flag:
            jam_det += 1

    return CampaignResult(
        n=n,
        fa_rate_full=fa_full / n,
        fa_rate_raim=fa_raim / n,
        availability=avail / n,
        median_hpl=float(np.median(hpls)),
        sf_detect_rate=sf_det / n,
        sf_exclude_correct_rate=(sf_corr / sf_det if sf_det else float("nan")),
        sf_err_before=float(np.median(err_before)),
        sf_err_after=float(np.median(err_after)) if err_after else float("nan"),
        sf_hmi_raim=sf_hmi,
        spoof_detect_raim=sp_raim / n,
        spoof_detect_full=sp_full / n,
        spoof_hmi_raim=sp_hmi_raim,
        spoof_hmi_full=sp_hmi_full,
        jam_detect_rate=jam_det / n,
        params={"pfa": rp.pfa, "pmd": rp.pmd, "hal": rp.hal, "sigma": mp.sigma_ura},
    )
