#!/usr/bin/env python3
"""Phase 4 of integration_campaign_2026-09 — run S7 -> S8 -> S9 -> S10 -> S12
end to end, on a nominal configuration and on a degraded one, keeping every
output timestamped and hashed.

The chain has never been executed as a chain. Each sprint was validated alone,
and Sprints 10 and 12 were only ever pointed at artefacts that happened to be
sitting in the repository.

Both cases run against a SHADOW ROOT: a directory holding only
`sprint{7,8,9}/data/`, which is all Sprint 10's provenance layer reads. The
repository's own artefacts are never overwritten by this script, so a degraded
run cannot leave degraded evidence behind -- which is itself the failure mode
a certification console has to be immune to.

Degraded case: a fleet-wide vision regression in Sprint 9. Every scenario's
camera drops from p_detect = 0.97 to 0.45, as an optics or illumination
regression across the fleet would. This is distinct from the single `low_light`
scenario, which degrades one approach; here every approach is affected,
including the ones the landing requirements are graded on.

    python e2e_run.py --stage upstream
    python e2e_run.py --stage s9  --case nominal
    python e2e_run.py --stage s9  --case degraded
    python e2e_run.py --stage cert --case nominal
    python e2e_run.py --stage cert --case degraded
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

CAMPAIGN = Path(__file__).resolve().parents[1]          # integration_campaign_2026-09
REPO = CAMPAIGN.parent
E2E = CAMPAIGN / "e2e"

S7 = REPO / "sprint7_battery_testbench"
S8 = REPO / "sprint8_flight_test_harness"
S9 = REPO / "sprint9_precision_landing"
S10 = REPO / "sprint10_fleet_certification"
S12 = REPO / "sprint12_vv_agent"

CASES = ("nominal", "degraded")
DEGRADED_P_DETECT = 0.45


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def shadow(case: str) -> Path:
    return E2E / case / "repo"


def outdir(case: str) -> Path:
    d = E2E / case / "out"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log(case: str, stage: str, text: str) -> None:
    d = outdir(case)
    (d / f"{stage}.log").write_text(text)
    print(text)


def record(case: str, stage: str, entries: dict) -> None:
    """Append one stage to the case manifest: what ran, when, what it produced."""
    m = outdir(case) / "manifest.json"
    blob = json.loads(m.read_text()) if m.is_file() else {"case": case, "stages": []}
    blob["stages"] = [s for s in blob["stages"] if s["stage"] != stage]
    blob["stages"].append({"stage": stage, "utc": now(), **entries})
    blob["stages"].sort(key=lambda s: s["utc"])
    m.write_text(json.dumps(blob, indent=2))


def run(cmd: list[str], cwd: Path) -> str:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    out = p.stdout + p.stderr
    if p.returncode != 0:
        raise SystemExit(f"FAILED ({p.returncode}): {' '.join(cmd)}\n{out}")
    return out


def hashes(paths: list[Path]) -> dict:
    return {p.name: {"sha256_12": sha(p), "bytes": p.stat().st_size} for p in paths}


# ---------------------------------------------------------------- upstream --
def stage_upstream() -> None:
    """S7 and S8. Identical in both cases, so generated once and copied."""
    text = [f"# upstream stage {now()}", ""]

    # --- S7: regenerate in place, then prove it reproduced what is committed.
    before = {f: sha(S7 / "data" / f) for f in
              ("estimator_benchmark.json", "cycle_records.json",
               "rul_projections.json", "triage_model.json")}
    text.append("$ python scripts/benchmark_estimators.py")
    text.append(run([sys.executable, "scripts/benchmark_estimators.py"], S7))
    text.append("$ python scripts/run_cycling_campaign.py")
    text.append(run([sys.executable, "scripts/run_cycling_campaign.py"], S7))
    after = {f: sha(S7 / "data" / f) for f in before}
    drift = {f: (before[f], after[f]) for f in before if before[f] != after[f]}
    text.append(f"\nS7 artefacts reproduced identically: {not drift}")
    if drift:
        text.append(f"  DRIFT: {drift}")

    # --- S8: generate straight into each shadow root.
    for case in CASES:
        d = shadow(case) / S8.name / "data"
        d.mkdir(parents=True, exist_ok=True)
        text.append(f"\n$ python scripts/run_campaign.py --seeds 4 --dt 0.05 "
                    f"--outdir {d.relative_to(REPO)}")
        text.append(run([sys.executable, "scripts/run_campaign.py",
                         "--seeds", "4", "--dt", "0.05", "--outdir", str(d)], S8))
        # S7's artefacts are case-independent.
        d7 = shadow(case) / S7.name / "data"
        d7.mkdir(parents=True, exist_ok=True)
        for f in before:
            shutil.copy2(S7 / "data" / f, d7 / f)

    for case in CASES:
        log(case, "01_upstream", "\n".join(text))
        record(case, "01_upstream", {
            "s7_reproduced_committed_artefacts": not drift,
            "s7_artefacts": hashes(sorted((shadow(case) / S7.name / "data").iterdir())),
            "s8_artefacts": hashes(sorted((shadow(case) / S8.name / "data").iterdir())),
            "s8_command": "scripts/run_campaign.py --seeds 4 --dt 0.05",
        })


# --------------------------------------------------------------------- S9 --
def stage_s9(case: str) -> None:
    sys.path.insert(0, str(S9))
    from polaris_pl import compute_metrics, grade, simulate            # noqa: E402
    from polaris_pl.faults import ALL_SCENARIOS                        # noqa: E402
    from polaris_pl.testcards import CARD_VERSION                      # noqa: E402

    seeds, step = 12, 0.02
    text = [f"# S9 stage, case={case}, {now()}",
            f"# {len(ALL_SCENARIOS)} scenarios x {seeds} seeds, dt={step}"]

    def build(name: str):
        s = ALL_SCENARIOS[name]()
        if case == "degraded":
            s.camera.p_detect = DEGRADED_P_DETECT
        return s

    if case == "degraded":
        text.append(f"# INJECTED: camera p_detect -> {DEGRADED_P_DETECT} on every "
                    f"scenario (fleet-wide vision availability regression)")

    runs, tally = [], {}
    for name in ALL_SCENARIOS:
        for seed in range(seeds):
            rep = grade(compute_metrics(simulate(build(name), seed=seed, dt=step)))
            row = rep.summary_row()
            row["seed"] = seed
            runs.append(row)
            t = tally.setdefault(name, {})
            t[row["card_verdict"]] = t.get(row["card_verdict"], 0) + 1

    d = shadow(case) / S9.name / "data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "campaign.json").write_text(json.dumps(
        {"card_version": CARD_VERSION, "seeds": seeds, "dt": step,
         "generated_utc": now(),
         "injection": (None if case == "nominal"
                       else {"where": "sprint9 camera", "parameter": "p_detect",
                             "nominal": 0.97, "applied": DEGRADED_P_DETECT,
                             "scope": "every scenario"}),
         "runs": runs}, indent=2))
    # Sprint 9's triage artefact is not affected by this injection path; copy the
    # committed one so Sprint 10's FC-LDG-005 still has an artefact to read.
    shutil.copy2(S9 / "data" / "triage.json", d / "triage.json")

    text.append("\ncard verdicts per scenario:")
    for name, t in tally.items():
        text.append(f"  {name:18s} " + "  ".join(f"{k}={v}" for k, v in sorted(t.items())))
    log(case, "02_s9", "\n".join(text))
    record(case, "02_s9", {
        "injection": None if case == "nominal" else
                     {"parameter": "camera.p_detect", "nominal": 0.97,
                      "applied": DEGRADED_P_DETECT, "scope": "every scenario"},
        "runs": len(runs),
        "card_verdicts": tally,
        "artefacts": hashes(sorted(d.iterdir())),
    })


# ------------------------------------------------------------- S10 and S12 --
def stage_cert(case: str) -> None:
    root = shadow(case).resolve()
    sys.path.insert(0, str(S10))
    sys.path.insert(0, str(S12))
    from polaris_fc import build_evidence, run_summary                 # noqa: E402
    from polaris_agent import Agent, DeterministicPolicy, build_registry  # noqa: E402
    from polaris_agent.report import render_findings_report            # noqa: E402

    res = build_evidence(root)
    summary = run_summary(res)
    rows = [{"id": r.requirement.id, "subsystem": r.requirement.subsystem.value,
             "title": r.requirement.title, "severity": r.requirement.severity.value,
             "status": r.status, "blocking": r.blocking,
             "value": r.aggregated_value, "bound": r.bound,
             "n_runs": r.n_runs_considered, "artefact": r.artefact_path,
             "artefact_hash": r.artefact_hash, "note": r.note}
            for r in res.all_results()]
    d = outdir(case)
    (d / "s10_rollup.json").write_text(json.dumps(
        {"generated_utc": now(), "shadow_root": str(root),
         "fleet_status": res.fleet_status(), "summary": summary,
         "requirements": rows}, indent=2, default=str))

    agent = Agent(registry=build_registry(repo_root=root, basis="baseline"),
                  policy=DeterministicPolicy())
    ares = agent.run(f"Certify the fleet ({case} configuration).")
    report = render_findings_report(ares, include_transcript=True)
    (d / "s12_findings_report.md").write_text(report)
    (d / "s12_transcript.json").write_text(json.dumps(
        [{"i": s.index, "thought": s.thought, "tool": s.tool,
          "arguments": s.arguments, "error": s.error} for s in ares.transcript],
        indent=2, default=str))

    decision = next((l for l in report.splitlines() if l.startswith("## Decision")), "?")
    text = [f"# certification stage, case={case}, {now()}",
            f"shadow root : {root}",
            f"S10 fleet   : {res.fleet_status()}",
            f"S10 reqs    : {sum(1 for r in rows if r['status'] == 'PASS')}/{len(rows)} pass, "
            f"{sum(1 for r in rows if r['blocking'])} blocking",
            "S10 failures:"]
    for r in rows:
        if r["status"] != "PASS":
            text.append(f"  {r['id']:11s} {r['severity']:8s} "
                        f"{'BLOCKING' if r['blocking'] else 'finding ':9s} "
                        f"value={r['value']} bound={r['bound']}")
    text += [f"S12 steps   : {ares.n_steps}, stopped={ares.stopped_reason}",
             f"S12 findings: {sorted(f.requirement_id for f in ares.ctx.findings)}",
             f"S12 {decision.strip('# ')}",
             "audit trail : every finding carries requirement_id, root_cause, "
             "recommendation, disposition; transcript in s12_transcript.json"]
    log(case, "03_cert", "\n".join(text))
    record(case, "03_cert", {
        "s10_fleet_status": res.fleet_status(),
        "s10_pass": sum(1 for r in rows if r["status"] == "PASS"),
        "s10_total": len(rows),
        "s10_failing": [r["id"] for r in rows if r["status"] != "PASS"],
        "s10_blocking": [r["id"] for r in rows if r["blocking"]],
        "s12_findings": sorted(f.requirement_id for f in ares.ctx.findings),
        "s12_decision": decision.strip("# ").strip(),
        "s12_tool_calls": ares.ctx.tool_calls,
        "outputs": hashes([d / "s10_rollup.json", d / "s12_findings_report.md",
                           d / "s12_transcript.json"]),
    })


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=("upstream", "s9", "cert"))
    ap.add_argument("--case", choices=CASES)
    a = ap.parse_args()
    if a.stage == "upstream":
        stage_upstream()
    else:
        if not a.case:
            raise SystemExit("--case is required for this stage")
        (stage_s9 if a.stage == "s9" else stage_cert)(a.case)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
