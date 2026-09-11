# Polaris S7 → S12 Toolchain Integration Report

| | |
|---|---|
| **Document** | Integration and verification of the Polaris evidence toolchain |
| **Version** | 1.0 |
| **Date** | 2026-09-11 |
| **Campaign** | `integration_campaign_2026-09`, phases 0 to 6, executed 2026-09-06 to 2026-09-11 |
| **Subject** | Sprint 7 → Sprint 8 → Sprint 9 → Sprint 10 → Sprint 12 |
| **Prepared by** | A. Barbarin, Polaris Decision Modeling Studio |

---

## 0. Read this first

**Every input to this campaign is synthetic.** Sprints 7, 8, 9 and 10 run
entirely on simulator-generated data: a Thévenin cell model, a fixed-wing
6-DoF with injected actuator and sensor faults, a multirotor approach model
with a synthetic camera, and the JSON artefacts those three write. No recorded
flight data, no bench data and no hardware were involved at any point.

This is therefore **verification and validation *of the toolchain***, not
validation of any vehicle, battery or algorithm against reality. Where this
report says a requirement passes, it means the console graded a number the
simulator produced against a bound a human wrote. It does not mean the
modelled behaviour is correct.

Two further limits on scope, stated up front because they constrain every
result below:

- The campaign ran on **Linux aarch64**, not on the macOS workstation where
  this repository is normally developed. The C++ cores were rebuilt and
  exercised as `.so`; the Makefiles' Darwin branch that produces `.dylib` was
  read but **never executed**, and the macOS-specific loader fallback was
  simulated at the loader level, not observed.
- Phases 0 to 2 reproduced defects without repairing them; phases 3 to 6
  repaired, re-ran and audited. The distinction is preserved per finding.

---

## 1. Configuration of record

| | |
|---|---|
| Host | Linux 6.8.0-136-generic **aarch64** (Cowork workspace VM) |
| Compiler | g++ (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0, `-O2 -std=c++17 -fPIC -Wall -Wextra` |
| Python | CPython 3.10.12, venv outside the repository |
| Packages | numpy 2.2.6, scipy 1.15.3, pandas 2.3.3, scikit-learn 1.7.2, matplotlib 3.10.9, pytest 9.1.1 |
| Repository | `github.com/Arthur-Barbarin/Polaris`, branch `main` |
| Baseline commit | `59aa64c` "new sprint on trajectory optimization" (campaign entry point) |
| Commits produced | `f3a4cad` (phase 0), `e430f02` (phase 1), `184ae93` (phase 2), and the phase 3-6 change set this report accompanies |
| Sprint 8 card version | 1.0.0 (unchanged) |
| Sprint 9 card version | 1.0.0 (criteria unchanged; **artefact schema changed** in phase 3, see O-10) |
| Sprint 10 catalogue | **1.0.0 → 1.1.0** (see F2-4) |

Artefact manifest at the close of the campaign, SHA-256 truncated to 12 hex
characters, as `sprint10_fleet_certification/polaris_fc/provenance.py` records
them:

| sha256_12 | bytes | artefact |
|---|---|---|
| `d20ce31af1c9` | 2 746 | `sprint7_battery_testbench/data/estimator_benchmark.json` |
| `241526c7e703` | 160 738 | `sprint7_battery_testbench/data/cycle_records.json` |
| `f8abd84ce8a2` | 124 | `sprint7_battery_testbench/data/rul_projections.json` |
| `260596e970ad` | 199 | `sprint7_battery_testbench/data/triage_model.json` |
| `3981f6f1b2f6` | 20 013 | `sprint8_flight_test_harness/data/campaign.json` |
| `0672ecb0bd53` | 4 258 | `sprint8_flight_test_harness/data/triage.json` |
| `fdf64a963d5c` | 80 663 | `sprint9_precision_landing/data/campaign.json` |
| `c02fd218f9da` | 508 | `sprint9_precision_landing/data/triage.json` |
| `942b0f0cc353` | 19 360 | `sprint7_battery_testbench/build/libpolaris_bms.so` |
| `7c0f0a174104` | 13 248 | `sprint8_flight_test_harness/build/libpolaris_ft.so` |

Raw console output for everything below is in
`integration_campaign_2026-09/logs/`, numbered in execution order; the probes
and runners are in `integration_campaign_2026-09/tools/`; the dated
run-by-run journal is `integration_campaign_2026-09/JOURNAL.md`.

---

## 2. What was executed

### 2.1 Environment and native path

```bash
cd sprint7_battery_testbench/cpp && make -B        # make clean fails: mount is delete-protected
cd sprint8_flight_test_harness/cpp && make -B
python -c "from polaris_bms import native as n; n._ocv(0.5)"        # 3.7
python -c "from polaris_ft import native as n; n._lib.ft_wrap_pi(7.0)"  # 0.7168146928204138
```

Both libraries rebuilt with zero warnings. The second command is the proof
that C++ actually executes rather than that `CDLL` merely succeeded:
7.0 − 2π = 0.7168146928204138.

### 2.2 Suites and verification scripts

```bash
python chain_gate.py            # all five suites + every read-only verify script
```

Final state, `logs/61_p6_final_gate.txt`:

```
  PASS  sprint7_battery_testbench     pytest                4.4s
  PASS  sprint8_flight_test_harness   pytest               31.9s
  PASS  sprint8_flight_test_harness   scripts/verify.py     6.4s
  PASS  sprint9_precision_landing     pytest               15.2s
  PASS  sprint9_precision_landing     scripts/verify.py    10.3s
  PASS  sprint10_fleet_certification  pytest                1.1s
  PASS  sprint10_fleet_certification  scripts/verify.py     0.0s
  PASS  sprint12_vv_agent             pytest                0.2s
  all 8 checks passed
```

Suite sizes moved from 18 / 28 / 19 / 21 / 18 at entry to **25 / 28 / 19 / 22
/ 18** at exit, all green.

### 2.3 Reproduction probes

```bash
python integration_campaign_2026-09/tools/s7_parity_probe.py       # native vs pure-Python mirror
python integration_campaign_2026-09/tools/s8_parity_margins.py     # measured, not asserted, margins
python integration_campaign_2026-09/tools/p1_kcyc_bisect.py        # locate the drifted fade coefficient
python integration_campaign_2026-09/tools/p1_krcyc_bisect.py       # and the resistance coefficient
python integration_campaign_2026-09/tools/p1_fa002_clip.py         # isolate the seeding defect
python integration_campaign_2026-09/tools/p2_contract_probe.py     # the S9/S10 collision
```

### 2.4 End-to-end campaign

```bash
python integration_campaign_2026-09/tools/e2e_run.py --stage upstream
python integration_campaign_2026-09/tools/e2e_run.py --stage s9   --case nominal
python integration_campaign_2026-09/tools/e2e_run.py --stage s9   --case degraded
python integration_campaign_2026-09/tools/e2e_run.py --stage cert --case nominal
python integration_campaign_2026-09/tools/e2e_run.py --stage cert --case degraded
```

Two configurations, each run against a **shadow root** holding only
`sprint{7,8,9}/data/`, so a degraded run cannot leave degraded evidence in the
repository. Every stage writes a timestamped, hashed manifest to
`integration_campaign_2026-09/e2e/<case>/out/manifest.json`.

- **Nominal** — S7 regenerated (and confirmed byte-identical to what is
  committed), S8 campaign at 4 seeds / dt 0.05, S9 campaign at 12 seeds /
  dt 0.02, then S10 and S12.
- **Degraded** — identical except that Sprint 9's camera `p_detect` is driven
  from 0.97 to **0.45 on every scenario**: a fleet-wide vision-availability
  regression, as an optics or illumination fault would produce. This is
  distinct from the existing `low_light` scenario, which degrades one approach.

### 2.5 Traceability audit

```bash
python integration_campaign_2026-09/tools/traceability_audit.py
python integration_campaign_2026-09/tools/traceability_audit.py --root integration_campaign_2026-09/e2e/degraded/repo
```

---

## 3. Findings

Eleven defects were reproduced by execution. Each is stated with the command that
reproduced it, its root cause, the correction applied, and the test that locks
it. Nothing below was written from a static reading alone.

### F1-1 — The committed battery model could not regenerate the committed dataset
**Sprint 7 · severity high · FIXED**

*Evidence.* `python scripts/run_cycling_campaign.py` produced final SoH 93.3 %
against the shipped 97.745 %, and RUL 80 cycles against the shipped 337. Every
figure in FA-001 derives from that dataset, so the report described a model no
longer in the repository.

*Root cause.* The loss ratio was a constant 2.96 from the first cycle, the
signature of a scaled coefficient. Bisecting on the pure-Python backend located
`k_cyc`, drifted from **0.0030 to 0.0090**; restoring it reproduced the SoH
trace exactly but left impedance-derived features 3-7 % off, and a second
bisection located `k_r_cyc`, drifted from **0.0008 to 0.0020**.

*Correction.* Both restored in `cpp/cell_model.hpp` and the Python mirror.

*Proof.* `cycle_records.json` and `rul_projections.json` now regenerate
**byte-identically**, and in-sample triage accuracy returns to the 94.6 % that
FA-001 has always quoted and that the drifted model could not produce (92.5 %,
then 94.2 % with only the first coefficient restored). Three independent
confirmations.

*Test.* `sprint7_battery_testbench/tests/test_dataset_reproducibility.py::test_committed_dataset_is_reproducible`,
parametrised over all five scenarios, pins seven features per cycle at
`rel=1e-9`. Verified to fail on the pre-fix code (5 failures,
`logs/22_p1_tests_fail_prefix.txt`).

### F1-5 — A seeding defect inflated the headline estimator result
**Sprint 7 · severity high · FIXED**

*Evidence.* `scripts/benchmark_estimators.py:62` clipped the initial guess to
`(0.05, 0.95)` while every scenario starts the cell at `soc0 = 1.0`, so the
**upper** bound seeded all three estimators 0.05 low in every run — including
`baseline_25c`, whose own table row declares a guess error of 0.0. Measured,
clip on versus clip removed, nothing else changed:

```
baseline, no bias at all, clip ON  : CC rms = 0.0496
baseline, no bias at all, clip OFF : CC rms = 0.0005
biased shunt (0.08 A), clip ON     : CC rms = 0.0761
biased shunt (0.08 A), clip OFF    : CC rms = 0.0285
```

*Root cause.* Open-loop coulomb counting cannot recover from a seed error; the
EKF re-anchors on voltage within seconds. The measured gap was the size of the
injected handicap, not a measure of filter quality.

*Correction.* The guard was widened to the physical range `(0.0, 1.0)` and
extracted into a documented `seed_guess()` so it can be tested. FA-002 was
reissued as rev B, **withdrawing its "+90 % average" headline**. Corrected:
the EKF is decisive on seed error (+98.7 %, +97.7 %) and at temperature
extremes (+74.3 %, +86.6 %), does not help on a clean run (CC 0.0002 vs EKF
0.0003), and is **twice as bad as open-loop counting under pure shunt bias**
(0.0287 vs 0.0575) because its state vector `[SOC, v_rc1, v_rc2]` carries no
current-bias term.

*Test.* `test_seed_guard_does_not_invent_a_guess_error`, verified to fail on
the pre-fix code with `assert 0.95 == 1.0`.

### F1-2 / F1-3 / F1-4 / F1-6 — Four false statements in FA-001
**Sprint 7 · severity medium · FIXED (report, not code)**

| | rev A claimed | measured | which was wrong |
|---|---|---|---|
| F1-2 | campaign at −10 °C (263.15 K) | 283.15 K, proven by the byte-identical reproduction at that temperature | the report |
| F1-3 | 1000-sample bootstrap CI 335 / 342 | `grep -rni bootstrap` finds the claim and no code; `rul_projection` is a bare `np.polyfit` | the report |
| F1-4 | RUL 339 | 337, which is what the code returns and what the JSON has always held | the report |
| F1-6 | mean cluster posterior 0.93 | **1.000** on every cycle; the GMM saturates and the posterior carries no confidence information | the report |

The bootstrap interval was **withdrawn, not recomputed**: implementing a
bootstrap to retro-fit a published number would be inventing the evidence a
second time. FA-001 was reissued as rev B with an explicit §0 revision notice.

### F1-7 — Sprint 8's README misreported one scenario
**Sprint 8 · severity low · FIXED**

`scripts/run_campaign.py --seeds 4 --dt 0.05` gives `thrust_loss` cross-track
**1.15 / 10.00**; the README read 1.24 / 15.1, within rounding of the nominal
row. Every other cell of that table, seven scenarios and five columns,
reproduces exactly as printed.

### F2-1 — Sprint 9's card verdict never reached any consumer
**Sprint 9 · severity high · FIXED — the campaign's centrepiece**

*Evidence.* Sprint 9 scores a landing on two axes that are both called
`outcome` in their own class: the **card verdict** (`PASS | FAIL | REJECT |
TIMEOUT`, `LandingReport.outcome`) and the **flight outcome** (`LANDED |
GO_AROUND | TIMEOUT`, `LandingMetrics.outcome`). `summary_row()` wrote the
verdict under `"outcome"` and then splatted `**self.metrics.as_dict()` over it.
The splat landed last.

```
  LandingReport.outcome  (card verdict, in memory) : {'PASS': 27, 'REJECT': 8, 'FAIL': 5}
  summary_row()['outcome'] (what serialises)       : {'LANDED': 32, 'GO_AROUND': 8}
  runs whose card verdict does NOT survive         : 40 / 40
  observed pairs: [('FAIL','LANDED'), ('PASS','LANDED'), ('REJECT','GO_AROUND')]
```

The shipped `campaign.json` contained no `PASS`, `FAIL` or `REJECT` token at
all. Reconstructed, the 120 runs were 83 PASS, 13 FAIL, 24 REJECT — and on the
field Sprint 10 read, the **13 card-FAIL runs**, landings that should not have
happened that way, were indistinguishable from the 83 clean ones.

*Root cause.* The two vocabularies overlap on exactly one token, `TIMEOUT`,
which is why the overwrite was silent on timeout runs and invisible everywhere
else. Both scores sharing an attribute name made the collision a one-character
oversight rather than a type error.

*Correction.* `summary_row()` now emits `card_verdict` and `flight_outcome`
under names that say which is which, and the ambiguous `outcome` key is
**removed**, so no consumer can read one while meaning the other. Regenerating
with the artefact's own recorded parameters (`--seeds 12 --dt 0.02`) gives 83
PASS / 13 FAIL / 24 REJECT, exactly the reconstruction, with **every shared
field bit-identical to the previous artefact**: the fix changed the schema and
not one measurement.

*Test.* `sprint10_fleet_certification/tests/test_s9_s10_contract.py`, nine
tests spanning both sprints. Committed in phase 2 under `xfail(strict=True)`;
the strict marker turned them into failures the moment the contract was
honoured, which is what forced the markers off in phase 3. The raw phase-2
failures are preserved in `logs/33_p2_contract_test_raw.txt`.

### F2-2 — Sprint 10 depended on that defect
**Sprint 10 · severity high · FIXED**

*Evidence.* `evidence.py:204-209` graded **FC-LDG-003**, a CRITICAL
requirement whose rationale says the guidance "MUST **reject** the landing", by
comparing `r.get("outcome")` against `"GO_AROUND"` and `"LANDED"`. It was
correct only because Sprint 9 overwrote the verdict with the flight outcome.
Renaming Sprint 9's field alone would have broken it immediately — which is
why the fix had to be made on both sides in one change.

*Correction.* FC-LDG-003 now checks **both** fields, each for what it means:
every unsafe run must be graded `REJECT` **and** must not have physically
landed. A run that landed while graded REJECT, or vice versa, is a scoring
defect the requirement now surfaces instead of absorbing. On an artefact that
predates the fix it **refuses to grade at all**, returning an explicit
"cannot evidence this requirement" rather than silently falling back.

### F2-3 — Sprint 9's dashboard rendered 0 of 120 runs
**Sprint 9 · severity medium · FIXED**

The panel its own docstring calls the "Campaign PASS / FAIL / REJECT matrix"
grouped on the missing field, so `dashboard/app.py:194-199` produced a 10 × 4
grid of zeros. The defensive `fill_value=0` and `if col not in mat` guard are
what turned a missing field into a plausible table rather than an error. Now
grouped on `card_verdict`, with a visible warning when the artefact predates
the field.

### F2-4 — A correct upstream fix silently failed a downstream requirement
**Sprints 7 → 10 → 12 · severity high · FIXED**

*Evidence.* F1-5's correction moved the mean EKF advantage from **90.06 % to
41.26 %**. FC-BAT-002 required ≥ 60 %. Consequence: Sprint 10's `verify.py`
exited 1, Sprint 10 lost one test, and **Sprint 12 lost five** — the fleet went
GREEN → FINDINGS and the decision GO → GO WITH FINDINGS. That regression was
pushed to `origin/main`.

*Root cause, two layers.* Proven causally by swapping
`estimator_benchmark.json` back to `e430f02^` and changing nothing else:

| artefact | mean advantage | S10 `verify.py` | S10 suite | S12 suite |
|---|---|---|---|---|
| pre-phase-1 | 90.06 % | PASS | 16 passed, 5 xfailed | 18 passed |
| phase-1 corrected | 41.26 % | FAIL | 1 failed | 5 failed |

The process layer: **phase 1's own regression check ran only the two sprints it
had edited**, not the four that consume their artefacts. The design layer:
FC-BAT-002's 60 % bound had no documented provenance, was duplicated in
`tests/test_certification.py`, and aggregated with `mean` — the exact statistic
FA-002 rev B withdrew.

*Correction.* Re-expressed rather than re-baselined.

- **FC-BAT-002** now reads `__ekf_advantage_where_required__`: a **worst-case**
  bound of ≥ 60 % over the conditions a closed-loop estimator exists to handle
  (a declared initial-guess error, or an off-nominal soak temperature). Worst
  case **74.3 %**, passes with margin, and a clean 25 °C run with a correct
  seed is explicitly out of scope.
- **FC-BAT-005** is split out: `__ekf_never_worse_than_open_loop__`, worst case
  over **every** condition ≥ 0 %. It measures **−100.0 %** and **fails by
  design**, as a MAJOR, non-blocking, tracked finding, so that the shunt-bias
  deficiency cannot be averaged away a second time.
- The bound is no longer duplicated: the test reads it from the requirement.
- `CATALOG_VERSION` **1.0.0 → 1.1.0**, because an evidence package tagged 1.0.0
  was graded against different requirements and is not comparable.
- Sprint 12's expectations were updated to the honest state: the baseline basis
  now carries exactly one standing finding and returns **GO WITH FINDINGS**,
  not an unqualified GO.
- `chain_gate.py` was added at the repository root, running all five suites and
  every read-only verification script in upstream-to-downstream order.

*Test.* `test_battery_ekf_never_worse_is_a_tracked_finding` asserts FC-BAT-005
fails **and** does not block, with a comment telling a future reader to invert
it deliberately if the estimator is ever improved. And the gate itself was
verified against this exact defect: re-introducing the pre-phase-1 artefact
turns it red on Sprint 10 and Sprint 12 with Sprint 7, 8 and 9 still green —
the signature it is built to catch, plus the hint it prints
(`logs/45_p3_gate_catches_f2-4.txt`).

### F2-5 — Sprint 7's README still publishes withdrawn numbers
**Sprint 7 · severity high (published state) · NOT FIXED**

The "Key results from the bundled data set" table is still rev A. Two rows are
stale, and they are exactly the two F1-5 predicted would move:

| scenario | published | measured |
|---|---|---|
| baseline (25 °C, clean sensors) | CC 0.050, EKF 0.002, **+97 %** | CC 0.0002, EKF 0.0003, **−9.7 %** |
| biased current shunt (+80 mA) | CC 0.076, EKF 0.011, **+86 %** | CC 0.0287, EKF 0.0575, **−100.0 %** |
| mean across 6 scenarios | **+90 % / +89 %** | +41.3 % / −196.2 %, and withdrawn |

Plus a triage `overall` of 95 % against FA-001's 94.6 %, and a "cold-soak
cycling" attribution that F1-2 disproved. Left unfixed deliberately: the
numbers are unambiguous, but how a portfolio README presents a −9.7 % and a
−100.0 % row is an editorial decision, not a V&V one.

### F3-1 — Sprint 9's artefact is not reproducible from the documented command
**Sprint 9 · severity low · NOT FIXED**

`scripts/run_campaign.py` defaults to `--seeds 20`; the committed
`campaign.json` records `"seeds": 12`. Running the documented command produces
200 runs against the committed 120 and changes every downstream number. The
parameters are at least recorded *in* the artefact, which is how this was
caught and how the phase-3 regeneration was kept schema-only.

### F3-3 — Sprint 9's triage artefact is not reproducible across runs
**Sprints 9 → 10 · severity medium · NOT FIXED**

*Evidence.* Running `scripts/run_campaign.py --seeds 12 --dt 0.02` three times
in a row gives a **byte-stable `campaign.json` and an unstable `triage.json`**.
Between two consecutive identical runs the cluster-to-label map flipped:

```
  campaign.json byte-stable across runs: True
  run1 vs run2: overall_accuracy same=True  per_class same=True
  run2 vs run3: overall_accuracy same=True  per_class same=False
     differing classes: {'NOMINAL': ([12,12],[0,12]), 'CROSSWIND': ([0,12],[12,12])}
```

*What was established, and what was not.* The fit is deterministic **within** a
process — five consecutive fits on the same metrics give one identical label
map — and varies **across** processes. `LandingTriage` already passes
`random_state=0` to both PCA and the GMM, with `n_init=3`, so the seed is set
and is not sufficient. Pinning BLAS to a single thread does not remove it
either: four single-threaded processes still produced two different maps.
Cluster 1 is a near-tie between `NOMINAL` and `CROSSWIND`, and the tie resolves
differently run to run. **The mechanism behind that tie-break was not
established** and is not guessed at here.

*Why it matters downstream.* Sprint 10's **FC-LDG-005** counts fault families
with at least one correct identification, excluding NOMINAL, against a bound of
**exactly 8**. Measured on the two observed triage states:

```
  per_class NOMINAL=[0,12] CROSSWIND=[12,12]  ->  FC-LDG-005 = 9 (bound 8.0, PASS)
  per_class NOMINAL=[12,12] CROSSWIND=[0,12]  ->  FC-LDG-005 = 8 (bound 8.0, PASS)
```

A certification requirement is therefore graded on a value that depends on
which of two identical runs last wrote the artefact, and in one of the two
states it passes with **zero margin**. One more confusable family and the fleet
verdict would flip run to run.

*Not fixed.* Making the tie-break deterministic is a change to the triage's
label-assignment rule, and doing it without first establishing why
`random_state` is insufficient would be guessing. Recorded as O-12.

### F4-1 — The fleet decision is insensitive to the landing cards' own verdicts
**Sprints 9 → 10 · severity high · NOT FIXED**

*Evidence.* The degraded end-to-end configuration drives Sprint 9's
`vision_avail_final` from 0.968 to 0.434, below the 0.7 card bound, so **every
nominal approach fails its acceptance cards**: 120 runs, **92 FAIL, 28 REJECT,
zero PASS**. Sprint 10 nonetheless grades **12 of 14 requirements PASS with
zero blockers**, and Sprint 12 returns **GO WITH FINDINGS** — the same decision
as the healthy configuration.

*Root cause.* Sprint 10 caught the *cause* and not the *consequence*.
FC-LDG-004 reads `vision_avail_final` directly and does fail (0.0 against a 0.9
bound), but it is MAJOR, so nothing blocks. Meanwhile FC-LDG-001 (touchdown
lateral, CRITICAL) still passes at 0.085 m against 0.5 m, because a
vision-starved approach in this model still touches down accurately. **No
requirement reads the card verdict for any scenario except the two unsafe ones
used by FC-LDG-003.** The aggregate verdict that phase 3 just made visible has
no consumer.

*Not fixed.* Adding a requirement over the nominal card verdict, or raising
FC-LDG-004 to CRITICAL, changes what the console certifies. That is a
requirements decision for the owner, not a defect repair, and this campaign's
rule was to fix only what it found broken.

---

## 4. Traceability breaks

`tools/traceability_audit.py` walks, for all 14 requirements, the chain
*requirement → test card → measurement → verdict → finding → anomaly cluster →
artefact hash*, and reports links that do not exist. Run on the repository and
on the degraded end-to-end root. Three breaks, identical in both:

| severity | where | break |
|---|---|---|
| **HIGH** | catalogue | **8 of Sprint 9's 10 scenarios have their card verdict read by no requirement.** 13 runs are graded FAIL among them in the repository configuration, 92 in the degraded one. A landing can be failed by its own test cards and contribute nothing to the fleet decision. This is F4-1 seen from the traceability side. |
| LOW | FC-BAT-005 | The failing requirement has no anomaly cluster, and its artefact has no triage layer to join to. The root-cause hop of the chain does not exist for non-campaign evidence types; only seeded campaigns carry triage labels. |
| LOW | `cycle_records.json` | Present in the manifest and hashed, but referenced by no requirement result. Hashed evidence nothing is graded against. |
| MEDIUM | FC-LDG-005 | Its evidence artefact, Sprint 9's `triage.json`, is not reproducible across identical runs (F3-3), so the hash in the manifest identifies one of two possible artefacts rather than a deterministic function of the inputs. The graded value moves between 9 and 8 against a bound of 8. |

Everything else holds: all 14 requirements carry an artefact hash, all
campaign-backed evidence carries scenario and seed, every failing requirement
has a finding recorded against it with a root cause, a recommendation and a
disposition, and Sprint 12's transcript records every tool call with no errors
on either configuration (8 steps nominal, 11 degraded).

One quality observation rather than a break: Sprint 12's deterministic policy
templates its root-cause text per **subsystem**, so FC-BAT-005 — an estimator
requirement — is dispositioned with "determine whether the fade model or the
triage labelling is the driver", which belongs to a degradation requirement.
The disposition and the numbers are right; the sentence is not.

---

## 5. End-to-end results

| | nominal | degraded (vision `p_detect` 0.97 → 0.45 fleet-wide) |
|---|---|---|
| S9 card verdicts | 120 PASS/FAIL/REJECT = 83 / 13 / 24 | **0 / 92 / 28** |
| S9 `vision_avail_final`, nominal scenario | 0.968 | 0.434 |
| S10 fleet status | FINDINGS | FINDINGS |
| S10 requirements | 13/14 pass, 0 blocking | 12/14 pass, 0 blocking |
| S10 failures | FC-BAT-005 | FC-BAT-005, FC-LDG-004 |
| S12 findings | FC-BAT-005 | FC-BAT-005, FC-LDG-004 |
| S12 decision | GO WITH FINDINGS | GO WITH FINDINGS |
| S12 steps / errors | 8 / none | 11 / none |

Sprint 12 produced a complete findings report on both configurations, each
finding carrying the requirement id, the criterion, the measured value, the
worst run, an analyst root cause and recommendation, a disposition, the
artefact path and its hash.

**Is the go/no-go coherent with the upstream verdicts? On the nominal case
yes; on the degraded case no.** The decision is identical in a configuration
where every nominal landing failed its own acceptance cards. That is F4-1, and
it is the most important thing this campaign found that it did not fix.

---

## 6. Open items

| # | Item | Why it is open |
|---|---|---|
| O-1 | `.dylib` artefacts never produced; the Makefiles' Darwin branch is unexecuted | No macOS shell was available. The macOS fallback was simulated at the loader level, never observed. |
| O-2 | Sprint 7 has no test that touches the C++ backend | With the core absent, Sprint 7 still runs green with no warning and no skip (F0-2). Writing that coverage was out of every phase's brief. |
| O-3 | Sprint 8's module-level skip hides 11 parity tests behind one `SKIPPED` line | Works as designed, reports badly: 28 passed becomes 17 passed + 1 skipped, exit 0. |
| O-4 | Neither `k_cyc = 0.0030` nor `k_r_cyc = 0.0008` is traceable to a physical calibration | Restored because reproducibility was the defect. The values themselves remain unjustified either way. |
| O-5 | Why the EKF is *worse* than the counter under shunt bias, not merely equal | Reproduced and reported. The absence of a current-bias state explains why it cannot reject the bias, not why it ends up behind. Adding a 4th state is a design change. |
| O-6 | `baseline_25c` now seeds the exact true SOC | Physically unrealistic, but it is what a declared guess error of 0.0 means. Starting the cell at `soc0 = 0.9` would fix the design. |
| O-7 | F2-5: Sprint 7's README table | Editorial decision, see the finding. |
| O-8 | F3-1: Sprint 9's `--seeds` default disagrees with its committed artefact | One-line fix, but changing a default silently changes every downstream number; it deserves its own change. |
| O-9 | F4-1: no requirement grades the nominal card verdict | A requirements decision, not a defect repair. |
| O-10 | Sprint 9's artefact schema changed while `CARD_VERSION` stayed 1.0.0 | Defensible — the card *criteria* did not change — but nothing records the schema change. Sprint 10's explicit `card_verdict` guard covers the failure mode today. |
| O-11 | The chain gate is not wired to CI | It exists and is verified to catch F2-4's class of defect, but it still has to be run by hand. |
| O-12 | F3-3: Sprint 9's triage is not reproducible across runs | `random_state=0` is already set and is not sufficient; single-threaded BLAS does not fix it. The mechanism was not established, and a tie-break change made without understanding it would be a guess. |

---

## 7. What this campaign does not prove

- **Nothing about reality.** Every input is simulator output. No result here
  supports a claim about a real cell, a real airframe, or a real approach.
- **Nothing about macOS.** The `.dylib` path is untested and the fallback was
  simulated.
- **Nothing about the models being right.** F1-1 restored the coefficients that
  generate the committed dataset; it did not validate either value.
- **Nothing about held-out performance.** Sprint 7's 94.6 % triage accuracy is
  in-sample, and F1-6 showed the posteriors that would normally qualify it are
  degenerate. Sprint 8's 100 % is near-tautological on 32 points.
- **Nothing about requirement adequacy.** The campaign verified that each
  requirement is graded against the measurement it names, from a hashed
  artefact. Whether the set of requirements is sufficient to certify anything
  is a different question, and F4-1 is direct evidence that it is not yet.
- **Nothing about the phases' own completeness.** Phase 1 declared "no
  regression" after running two of five suites and shipped F2-4. The gate now
  makes that specific mistake hard; it does not make the campaign exhaustive.

---

*Polaris Decision Modeling Studio · engineering clarity for complex futures.*
