"""Run a multi-fault accelerated cycling campaign and train the triage model.

Outputs:
  data/cycle_records.json   - per-cycle features for every fault scenario
  data/triage_model.json    - cluster->mode mapping
  data/rul_projections.json - RUL projection per scenario
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from polaris_bms import Fault
from polaris_bms.cycler import CycleRecord, run_cycling_campaign
from polaris_bms.triage import FailureTriage, rul_projection

OUT = REPO / "data"
OUT.mkdir(exist_ok=True)

SCENARIOS = [
    ("HEALTHY",                 Fault.NONE,                  0.0,  298.15, 60),
    ("LITHIUM_PLATING",         Fault.LITHIUM_PLATING,       0.8,  283.15, 60),
    ("SEI_GROWTH",              Fault.SEI_GROWTH,            0.7,  308.15, 60),
    ("INTERNAL_SHORT",          Fault.INTERNAL_SHORT,        0.6,  298.15, 60),
    ("ELECTROLYTE_DEPLETION",   Fault.ELECTROLYTE_DEPLETION, 0.9,  313.15, 60),
]


def main() -> None:
    all_records: List[CycleRecord] = []
    by_scenario: Dict[str, List[CycleRecord]] = {}
    print("Running cycling campaigns...")
    for label, fault, sev, T_k, n in SCENARIOS:
        recs = run_cycling_campaign(n_cycles=n, fault=fault, fault_severity=sev,
                                    temperature_k=T_k)
        for r in recs:
            r.fault = label
        all_records.extend(recs)
        by_scenario[label] = recs
        soh_end = recs[-1].soh_pct
        print(f"  {label:24s} -> {n} cycles, final SoH={soh_end:5.1f}%")

    # Write raw records
    with (OUT / "cycle_records.json").open("w") as f:
        json.dump([{**asdict(r)} for r in all_records], f, indent=2)

    # Train triage (drop the first cycle of each scenario - no delta features yet)
    training = [r for r in all_records if r.cycle > 1]
    triage = FailureTriage(n_components=4, n_clusters=8).fit(training)
    with (OUT / "triage_model.json").open("w") as f:
        json.dump({str(k): v for k, v in triage.cluster_to_label.items()}, f, indent=2)
    print(f"\nTriage clusters -> {triage.cluster_to_label}")

    # RUL projection per scenario
    rul = {}
    for label, recs in by_scenario.items():
        rul[label] = rul_projection(recs)
    with (OUT / "rul_projections.json").open("w") as f:
        json.dump(rul, f, indent=2)
    print(f"RUL projections (cycles to 80% SoH): {rul}")

    # Confusion-style accuracy on the training set
    preds = triage.predict(training)
    correct = sum(1 for p, r in zip(preds, training) if p.predicted_mode == r.fault)
    print(f"\nTriage in-sample accuracy: {correct}/{len(training)} "
          f"= {100*correct/len(training):.1f}%")
    # Per-class breakdown
    by_class = {}
    for p, r in zip(preds, training):
        d = by_class.setdefault(r.fault, [0, 0])
        d[1] += 1
        if p.predicted_mode == r.fault:
            d[0] += 1
    for k, (ok, total) in sorted(by_class.items()):
        print(f"  {k:24s} {ok}/{total} = {100*ok/total:.1f}%")


if __name__ == "__main__":
    main()
