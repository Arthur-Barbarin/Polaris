# Polaris Sprint 10 — Fleet Certification Console

A cross-subsystem traceability console that ingests the artefacts produced by
**Sprint 7** (battery testbench), **Sprint 8** (fixed-wing flight-test harness),
and **Sprint 9** (precision-landing studio), and presents them as a single
**requirement → test card → measurement → evidence → root-cause** matrix — the
way a V&V or DER package is actually organised.

Sprint 10 does **not** re-implement the physics of 7–9. It reads their
versioned outputs, grades each requirement against the metrics those sprints
already emit, hashes every artefact for provenance, and joins each failure to
the anomaly-triage cluster the responsible run landed in.

> **Honesty note.** Every underlying telemetry point comes from the sprint 7–9
> simulators, all of which are **synthetic**. This sprint produces certification
> *paperwork over synthetic evidence* — the goal is to demonstrate the
> traceability toolchain, not to certify a real aircraft.

## Why this exists

The sprints 7–9 arc each shows a self-contained V&V harness. What the arc
was missing is the **connective tissue** — the artefact a systems /
certification engineer keeps: one traceability matrix rolling every
subsystem's test cards up into a single go / no-go rollup, pinned to the
exact bytes it was computed from. That connective tissue is what this
sprint is.

## Architecture

```
   sprint7_battery_testbench/data/*.json  ┐
   sprint8_flight_test_harness/data/*.json├──►  polaris_fc.provenance
   sprint9_precision_landing/data/*.json  ┘       (SHA-256 + manifest)
                                                        │
                                                        ▼
                                    polaris_fc.requirements  (versioned catalog)
                                                        │
                                                        ▼
                                    polaris_fc.evidence      (grade + aggregate)
                                                        │
                                          ┌─────────────┴──────────────┐
                                          ▼                            ▼
                                Streamlit console            scripts/export_evidence.py
                                (5 tabs, inject-fault)        (one-page PDF package)
```

## Layout

```
sprint10_fleet_certification/
├── polaris_fc/
│   ├── requirements.py  versioned requirements catalog (subsystem, metric,
│   │                    bound, aggregation, severity, rationale)
│   ├── evidence.py      reads sprint 7-9 artefacts and grades each requirement;
│   │                    joins failures to anomaly-triage clusters
│   ├── provenance.py    SHA-256 (truncated) hashing + artefact manifest
│   └── inject.py        thin subprocess adapter over the source sprints'
│                        own run_campaign.py / run_cycling_campaign.py
├── dashboard/app.py     Streamlit: Overview / Traceability / Drill-in /
│                        Inject Fault / Provenance
├── scripts/
│   ├── export_evidence.py   one-page PDF certification evidence package
│   └── verify.py            reproduces every headline number
├── tests/test_certification.py    pytest gate (unit + integration)
├── requirements.txt
└── README.md
```

## Quickstart

```bash
pip install -r requirements.txt

# Verify the traceability numbers against the checked-in sprint 7-9 outputs.
python scripts/verify.py

# Run the pytest gate (unit + integration against the real artefacts).
python -m pytest -q

# Launch the console.
streamlit run dashboard/app.py

# Generate a one-page evidence PDF into ./reports/.
python scripts/export_evidence.py
```

## How the traceability matrix works

Each requirement in `polaris_fc/requirements.py` names:

- **`artefact_role`** — which sprint output it reads (`campaign`, `triage`,
  `estimator_benchmark`, `triage_model`, `rul_projections`, `cycle_records`).
- **`metric`** — which field to pull from that artefact.
- **`op` + `bound`** — the pass criterion (`<=`, `>=`, `==True`, `==False`,
  `pass_frac>=`).
- **`aggregate`** — how to fold many runs into one number (`worst_case`,
  `mean`, `pass_fraction`, `exists_pass`).
- **`severity`** — `CRITICAL` (blocks certification), `MAJOR` (waiverable
  finding), `MINOR` (informational).

A few requirements use metric names beginning with `__…__` — those are
**derived metrics** computed inside `evidence.py`, e.g.
`__unsafe_becomes_reject__` (verifies that Sprint 9's `gust` and
`vision_dropout` scenarios *all* triggered a `GO_AROUND` and *none* landed).
This is where the sprint-10 value-add sits: it lets one requirement span
several rows of a source artefact — the kind of check a reviewer actually
asks for that no single sprint's dashboard makes visible on its own.

## What's on each console tab

- **Overview** — fleet status band (GREEN / FINDINGS / BLOCKED),
  per-subsystem status, catalog version.
- **Traceability matrix** — one row per requirement, aggregated value,
  bound, PASS/FAIL, severity, artefact hash.
- **Requirement drill-in** — the full per-run evidence for one
  requirement, including which anomaly-triage cluster each run landed in.
- **Inject fault** — pick a source-sprint campaign, re-run it in-place;
  the matrix updates with the new numbers (and the new hashes) on the
  next reload.
- **Provenance & export** — the artefact manifest with hashes, and a
  one-click PDF evidence package.

## Sample headline (against the checked-in sprint 7-9 outputs)

Run `python scripts/verify.py` to reproduce. Expected output includes:

- `FC-BAT-002`: mean EKF advantage over coulomb counting ≥ 60 %
- `FC-UAV-001`: nominal fixed-wing mission passes at 100 %
- `FC-LDG-001`: nominal touchdown lateral error ≤ 0.5 m on every seed
- `FC-LDG-003`: every unsafe final (`gust`, `vision_dropout`) correctly
  aborted via `GO_AROUND` — zero landings

The requirements that are **expected** to fail against the current
artefacts are also visible in the console — they are the ones that
document the trade-space Sprints 7-9 already acknowledge (e.g. every UAV
fault-injection scenario deliberately busts a card; that failure is
*data*, not a bug).
