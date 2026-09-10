"""Phase 2: reproduce the S9 -> S10 contract collision by execution.

Hypothesis from static review: LandingReport.summary_row() in
sprint9_precision_landing/polaris_pl/testcards.py builds

    {"scenario":..., "label":..., "outcome": self.outcome, "passed":..., **self.metrics.as_dict()}

where self.outcome is the CARD VERDICT (PASS | FAIL | REJECT | TIMEOUT) and
self.metrics.as_dict() also carries a key named "outcome" holding the
OPERATIONAL outcome (LANDED | GO_AROUND | TIMEOUT). The splat lands last, so
the card verdict is overwritten and never serialised.

Nothing is fixed here. This only measures.
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
S9 = ROOT / "sprint9_precision_landing"
sys.path.insert(0, str(S9))

from polaris_pl import compute_metrics, grade, simulate            # noqa: E402
from polaris_pl.faults import ALL_SCENARIOS                        # noqa: E402

print("=" * 78)
print("1. Does grade() produce a card verdict distinct from the operational outcome?")
print("=" * 78)
rows, reports = [], []
for name, fn in ALL_SCENARIOS.items():
    for seed in range(4):
        rep = grade(compute_metrics(simulate(fn(), seed=seed, dt=0.02)))
        reports.append(rep)
        rows.append(rep.summary_row())

print(f"{len(reports)} runs, {len(ALL_SCENARIOS)} scenarios x 4 seeds")
print()
print("  LandingReport.outcome  (the card verdict, in memory) :",
      dict(Counter(r.outcome for r in reports)))
print("  metrics.outcome        (the operational outcome)     :",
      dict(Counter(r.metrics.outcome for r in reports)))
print("  summary_row()['outcome'] (what actually serialises)  :",
      dict(Counter(row["outcome"] for row in rows)))
print()

lost = [(r.outcome, row["outcome"]) for r, row in zip(reports, rows)
        if r.outcome != row["outcome"]]
print(f"  runs whose card verdict does NOT survive summary_row(): "
      f"{len(lost)} / {len(reports)}")
print(f"  verdict -> serialised value, observed pairs: {sorted(set(lost))}")
print()
print("  every key summary_row() sets and then loses to the splat:")
first = reports[0]
explicit = {"scenario", "label", "outcome", "passed"}
splatted = set(first.metrics.as_dict())
for k in sorted(explicit & splatted):
    print(f"    {k!r:12s} explicit={getattr(first, k)!r:12s} "
          f"splatted={first.metrics.as_dict()[k]!r:12s} "
          f"{'<== SILENTLY DIFFERENT' if getattr(first, k) != first.metrics.as_dict()[k] else '(same value, harmless)'}")
print(f"  keys set explicitly but never splatted (safe): "
      f"{sorted(explicit - splatted)}")

print()
print("=" * 78)
print("2. Is the card verdict present anywhere in the shipped artefact?")
print("=" * 78)
art = json.load(open(S9 / "data" / "campaign.json"))
runs = art["runs"]
print(f"  data/campaign.json: {len(runs)} runs, keys = {sorted(runs[0])}")
print(f"  'card_verdict' present : {'card_verdict' in runs[0]}")
print(f"  'verdict' present      : {'verdict' in runs[0]}")
print(f"  outcome values on disk : {dict(Counter(r['outcome'] for r in runs))}")
print(f"  passed values on disk  : {dict(Counter(r.get('passed') for r in runs))}")
print()
print("  the three card verdicts, as they would have been:")
print(f"    PASS   = passed True                       -> "
      f"{sum(1 for r in runs if r.get('passed'))}")
print(f"    REJECT = passed False and go_around True   -> "
      f"{sum(1 for r in runs if not r.get('passed') and r.get('go_around'))}")
print(f"    FAIL   = passed False and go_around False  -> "
      f"{sum(1 for r in runs if not r.get('passed') and not r.get('go_around'))}")
print("  none of those three strings appears in the artefact:")
blob = json.dumps(runs)
for tok in ("PASS", "FAIL", "REJECT", "TIMEOUT", "LANDED", "GO_AROUND"):
    print(f"    {tok:10s} in campaign.json runs: {tok in blob}")

print()
print("=" * 78)
print("3. Does S10 read the overwritten field?")
print("=" * 78)
S10 = ROOT / "sprint10_fleet_certification"
src = (S10 / "polaris_fc" / "evidence.py").read_text().splitlines()
for i, line in enumerate(src, 1):
    if 'get("outcome")' in line:
        print(f"  evidence.py:{i}: {line.strip()}")
print()
print("  FC-LDG-003 compares that field against 'GO_AROUND' / 'LANDED', i.e.")
print("  against the OPERATIONAL outcome, under a key whose documented meaning")
print("  in LandingReport is the card verdict. S10 is correct today only")
print("  because S9's splat overwrites the verdict.")
