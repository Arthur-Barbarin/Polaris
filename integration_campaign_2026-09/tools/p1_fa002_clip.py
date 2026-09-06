"""Phase 1, FA-002: what actually produces the coulomb-counter error?

FA-002 s3 says the biased_shunt RMS of 0.076 is 0.05 of integrated shunt bias
plus "0.026 from the wrong initial guess" -- while its own table gives that
scenario a guess error of 0.0.

benchmark_estimators.py:62 reads
    init_guess = float(np.clip(true_init - guess_err, 0.05, 0.95))
and the cell starts at soc0 = 1.0, so with guess_err = 0.0 the clip's UPPER
bound hands the estimators 0.95 against a true 1.00: an unrequested 0.05 seed
error in every scenario.

This re-runs two scenarios with the clip as written and with it removed,
changing nothing else, and reports the coulomb-counter RMS each way.
"""
import sys
from pathlib import Path
import numpy as np

S7 = Path(__file__).resolve().parents[2] / "sprint7_battery_testbench"
sys.path.insert(0, str(S7)); sys.path.insert(0, str(S7 / "scripts"))

from polaris_bms import Cell, CoulombCounter
from polaris_bms.signals import inject_current_noise
import benchmark_estimators as be

profile = be._profile_mixed(3600 * 2)

def cc_only(temperature_k, bias_a, guess_err, clip, dt=1.0, seed=13):
    rng = np.random.default_rng(seed)
    cell = Cell(soc0=1.0, temperature_k=temperature_k)
    true_init = cell.snapshot().soc
    raw = true_init - guess_err
    init_guess = float(np.clip(raw, 0.05, 0.95)) if clip else float(raw)
    cc = CoulombCounter(capacity_ah=cell.snapshot().q_now_ah, soc=init_guess)
    n = len(profile); true = np.empty(n); e_cc = np.empty(n)
    for k, i_true in enumerate(profile):
        cell.step(float(i_true), dt)
        cc.step(inject_current_noise(float(i_true), rng, std_a=0.01, bias_a=bias_a), dt)
        true[k] = cell.snapshot().soc; e_cc[k] = cc.soc
    warm = int(60 / dt)
    err = true[warm:] - e_cc[warm:]
    return init_guess, true_init, float(np.sqrt(np.mean(err ** 2)))

print(f"{'scenario':22s} {'bias':>5} {'guess_err':>9} {'clip':>6} "
      f"{'true soc0':>10} {'seed guess':>11} {'CC rms':>8}")
rows = {}
for label, T, bias, gerr in (("baseline_25c", 298.15, 0.0, 0.0),
                             ("biased_shunt_25c", 298.15, 0.08, 0.0)):
    for clip in (True, False):
        g, t0, rms = cc_only(T, bias, gerr, clip)
        rows[(label, clip)] = rms
        print(f"{label:22s} {bias:5.2f} {gerr:9.1f} {str(clip):>6} "
              f"{t0:10.3f} {g:11.3f} {rms:8.4f}")

print()
print(f"baseline, no bias at all, clip ON  : CC rms = {rows[('baseline_25c',True)]:.4f}"
      f"   <- pure artefact of the clip, zero bias applied")
print(f"baseline, no bias at all, clip OFF : CC rms = {rows[('baseline_25c',False)]:.4f}")
print(f"biased shunt (0.08 A), clip ON     : CC rms = {rows[('biased_shunt_25c',True)]:.4f}"
      f"   <- the 0.076 quoted in FA-002")
print(f"biased shunt (0.08 A), clip OFF    : CC rms = {rows[('biased_shunt_25c',False)]:.4f}"
      f"   <- what the shunt bias alone actually costs")
