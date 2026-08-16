import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gnss import run_campaign

# A small, fixed campaign shared across the metric tests.
R = run_campaign(300, seed=14)


def test_nominal_false_alarm_tracks_pfa():
    assert R.fa_rate_full < 0.02          # configured Pfa is 1e-3
    assert R.availability > 0.97


def test_single_fault_detected_and_excluded():
    assert R.sf_detect_rate > 0.95
    assert R.sf_exclude_correct_rate > 0.97
    assert R.sf_err_after < R.sf_err_before


def test_spoof_headline_raim_blind_monitor_catches():
    assert R.spoof_detect_raim < 0.02
    assert R.spoof_detect_full == 1.0
    assert R.spoof_hmi_full == 0          # no hazardous misleading info survives


def test_jamming_fully_detected():
    assert R.jam_detect_rate == 1.0


def test_campaign_is_reproducible():
    b = run_campaign(300, seed=14)
    assert b.sf_detect_rate == R.sf_detect_rate
    assert b.spoof_hmi_raim == R.spoof_hmi_raim
    assert b.spoof_detect_full == R.spoof_detect_full
