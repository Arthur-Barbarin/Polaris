#!/usr/bin/env python3
"""Phase 5 of integration_campaign_2026-09 — walk the full evidence chain for
every requirement and list the links that do not exist.

The chain a certification console claims to keep is

    requirement -> test card -> measurement -> verdict -> finding
                -> anomaly cluster -> artefact hash

This walks each link for every requirement in the catalogue, on whichever
shadow root it is pointed at, and reports where a link is missing rather than
assuming the console's own green status means the trail is complete.

    python traceability_audit.py                      # the repository itself
    python traceability_audit.py --root ../e2e/degraded/repo
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import sys

CAMPAIGN = Path(__file__).resolve().parents[1]
REPO = CAMPAIGN.parent
sys.path.insert(0, str(REPO / "sprint10_fleet_certification"))
sys.path.insert(0, str(REPO / "sprint12_vv_agent"))

from polaris_fc import build_evidence                                  # noqa: E402
from polaris_fc.provenance import artefact_manifest                    # noqa: E402
from polaris_agent import Agent, DeterministicPolicy, build_registry    # noqa: E402

CARD_VERDICTS = {"PASS", "FAIL", "REJECT", "TIMEOUT"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(REPO))
    a = ap.parse_args()
    root = Path(a.root).resolve()

    res = build_evidence(root)
    manifest = {(r.subsystem, r.role): r for r in artefact_manifest(root)}
    agent = Agent(registry=build_registry(repo_root=root, basis="baseline"),
                  policy=DeterministicPolicy())
    ares = agent.run("traceability audit")
    findings = {f.requirement_id: f for f in ares.ctx.findings}

    breaks: list[tuple[str, str, str]] = []      # (severity, id, description)
    print(f"=== traceability audit ===\nroot: {root}\n")
    hdr = (f"{'requirement':11s} {'sev':8s} {'stat':4s} {'card':5s} {'meas':5s} "
           f"{'seed':5s} {'clus':5s} {'find':5s} {'hash':5s}  note")
    print(hdr)
    print("-" * len(hdr))

    for r in res.all_results():
        req = r.requirement
        has_card = bool(r.evidence)
        # measurement: does each evidence item carry an actual value?
        has_meas = bool(r.evidence) and all(e.value is not None for e in r.evidence)
        # run identity: can a reader point at the exact run behind the number?
        has_seed = bool(r.evidence) and all(e.seed is not None for e in r.evidence)
        has_clus = bool(r.evidence) and any(e.triage_label for e in r.evidence)
        has_find = req.id in findings
        has_hash = bool(r.artefact_hash)

        def t(b):
            return " ok  " if b else " --  "

        print(f"{req.id:11s} {req.severity.value:8s} {r.status:4s} "
              f"{t(has_card)}{t(has_meas)}{t(has_seed)}{t(has_clus)}"
              f"{t(has_find)}{t(has_hash)}  {r.note[:46]}")

        # Only a seeded campaign has runs to point at. The battery artefacts are
        # one row per characterisation condition and the triage/RUL artefacts are
        # summaries, so "no seed" there is the artefact's shape, not a break.
        seeded_artefact = req.artefact_role == "campaign"

        if not has_hash:
            breaks.append(("HIGH", req.id,
                           "no artefact hash recorded on the result: the number "
                           "cannot be tied to a specific version of the evidence file"))
        if seeded_artefact and r.evidence and not has_seed:
            breaks.append(("HIGH", req.id,
                           "campaign-backed evidence carries no seed: a reader "
                           "cannot reach the individual run behind the aggregate"))
        if r.evidence and any(not e.scenario for e in r.evidence):
            breaks.append(("MEDIUM", req.id,
                           "evidence items carry no scenario identity"))
        if not r.passed and not has_find:
            breaks.append(("HIGH", req.id,
                           "requirement FAILS but the analyst recorded no finding"))
        if not r.passed and seeded_artefact and not has_clus:
            breaks.append(("MEDIUM", req.id,
                           "failing campaign-backed requirement has no anomaly-triage "
                           "cluster joined to any of its evidence"))
        if not r.passed and not seeded_artefact and not has_clus:
            breaks.append(("LOW", req.id,
                           "failing requirement has no anomaly cluster, and its "
                           "artefact has no triage layer to join to: the root-cause "
                           "hop of the chain does not exist for this evidence type"))

    # --- does anything consume Sprint 9's card verdict? ---------------------
    camp = root / "sprint9_precision_landing" / "data" / "campaign.json"
    if camp.is_file():
        runs = json.loads(camp.read_text())["runs"]
        verdicts = Counter(r.get("card_verdict") for r in runs)
        graded_on_verdict = [r.requirement.id for r in res.all_results()
                             if any(e.value in CARD_VERDICTS for e in r.evidence)]
        covered = set()
        for rr in res.all_results():
            if any(e.value in CARD_VERDICTS for e in rr.evidence):
                covered |= {e.scenario for e in rr.evidence}
        uncovered = sorted({r["scenario"] for r in runs} - covered)
        print(f"\nsprint 9 card verdicts on disk : {dict(verdicts)}")
        print(f"requirements graded on a verdict: {graded_on_verdict or 'NONE'}")
        print(f"scenarios whose verdict no requirement reads: {uncovered}")
        n_fail = sum(1 for r in runs if r.get("card_verdict") == "FAIL"
                     and r["scenario"] in uncovered)
        if uncovered:
            breaks.append((
                "HIGH", "catalogue",
                f"{len(uncovered)} of {len({r['scenario'] for r in runs})} sprint-9 "
                f"scenarios have their card verdict read by no requirement "
                f"({n_fail} runs currently graded FAIL among them). A landing can be "
                f"failed by its own test cards and contribute nothing to the fleet "
                f"decision."))

    # --- artefacts present but never referenced ----------------------------
    referenced = {Path(r.artefact_path).name for r in res.all_results()
                  if r.artefact_path}
    for (sub, role), rec in manifest.items():
        if rec.exists and rec.path.name not in referenced:
            breaks.append(("LOW", f"{sub}/{role}",
                           f"artefact {rec.path.name} is in the manifest and hashed "
                           f"but no requirement result references it"))

    print(f"\n=== traceability breaks: {len(breaks)} ===")
    for sev in ("HIGH", "MEDIUM", "LOW"):
        for s, rid, desc in breaks:
            if s == sev:
                print(f"  [{sev}] {rid}: {desc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
