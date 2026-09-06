# S7 → S12 Toolchain Integration Campaign — Execution Journal

**Campaign:** verification and integration of the Polaris evidence toolchain
(S7 battery testbench → S8 flight-test harness → S9 precision landing →
S10 fleet certification → S12 agentic V&V analyst).

**All data exercised in this campaign is synthetic**, produced by the sprint
simulators. This is V&V *of the toolchain*, not validation against real flight
data. Nothing here supports a claim about hardware behaviour.

**Rule applied throughout:** no number enters this journal unless a command run
during this campaign produced it. Statements that are inference rather than
measurement are labelled `INFERENCE`.

Raw console output for every entry below is under `logs/`. Probe scripts are
under `tools/`.

---

## Environment of record

| | |
|---|---|
| Host | Linux 6.8.0-136-generic **aarch64** (Cowork workspace VM on the operator's Mac) |
| Compiler | g++ (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0 |
| Python | CPython 3.10.12, venv at `$HOME/polaris_lnx_venv` (outside the repo) |
| Packages | numpy 2.2.6, scipy 1.15.3, pandas 2.3.3, scikit-learn 1.7.2, matplotlib 3.10.9, pytest 9.1.1 |
| Repo | `Polaris_sprint`, branch `main`, HEAD `e1a60d0` |
| Working tree | dirty on entry (pre-existing, unrelated modifications left untouched) |

### Scope limit that shapes all of Phase 0

The shell available for this campaign is a **Linux aarch64 VM**, not macOS.
The repository's `.venv` is a macOS pyenv 3.11.9 environment and cannot be
executed here; a separate Linux venv was built outside the repository instead.

Consequence, stated plainly:

- On this host, `platform.system() == "Linux"`, the loader looks for
  `libpolaris_*.so`, and those load. **The macOS-specific fallback was
  therefore not observed directly.** No claim is made that it was.
- What *was* reproduced by execution is the loader mechanism itself and every
  consequence that follows from it, by forcing the loader into the exact macOS
  condition (`platform.system() → "Darwin"`, so it searches for a `.dylib`
  that the repository does not contain). See P0-4.
- Producing the `.dylib` artefacts on macOS remains open. See "Open items".

---

## P0-1 — Rebuild both native libraries from source

**2026-09-06T18:36:32Z** — log: `logs/01_rebuild.txt`

```
cd sprint7_battery_testbench/cpp && make clean && make
cd sprint8_flight_test_harness/cpp && make clean && make
```

`make clean` **failed in both sprints**:

```
rm -rf ../build
rm: cannot remove '../build/libpolaris_bms.so': Operation not permitted
make: *** [Makefile:36: clean] Error 1
```

This is an environment property, not a repository defect: mounted folders in
this workspace are delete-protected. Overwrite is permitted, so a full
recompile-and-relink was forced without deletion:

```
cd sprint7_battery_testbench/cpp && make -B
cd sprint8_flight_test_harness/cpp && make -B
```

Both compiled and linked **with zero warnings** under `-Wall -Wextra`:

```
g++ -O2 -std=c++17 -fPIC -Wall -Wextra -Wno-unused-parameter -c cell_model.cpp -o ../build/cell_model.o
g++ -O2 -std=c++17 -fPIC -Wall -Wextra -Wno-unused-parameter -c ekf_soc.cpp   -o ../build/ekf_soc.o
g++ -O2 -std=c++17 -fPIC -Wall -Wextra -Wno-unused-parameter -c c_api.cpp     -o ../build/c_api.o
g++ -shared -o ../build/libpolaris_bms.so ../build/cell_model.o ../build/ekf_soc.o ../build/c_api.o
```

Artefact identity before and after the rebuild:

| artefact | md5 as found (Jun 29 / Jul 3) | md5 after `make -B` | BuildID changed |
|---|---|---|---|
| `libpolaris_bms.so` | `ef25810cbb2e5f6f8aaf566b0f5e541e` | `3ae442c31241fef8f0c3dc2ac70d6924` | yes |
| `libpolaris_ft.so` | `aa89fc6f2846f6ecf68db4853c06f40d` | `aa89fc6f2846f6ecf68db4853c06f40d` | no (byte-identical) |

Determinism was then checked directly by building S7 a second time and
comparing: the two rebuilds are byte-identical (`cmp` clean), no `__DATE__`,
`__TIME__` or `__FILE__` macro appears in either C++ tree, and the `.cpp`/`.hpp`
mtimes (Jun 29 23:13–23:33) predate the binary they supposedly produced.

`INFERENCE`: since the build is deterministic and the sources have not been
touched since the old binary was cut, the shipped `libpolaris_bms.so` was most
plausibly produced by a **different toolchain version**. This was not
established — the old build environment is gone and cannot be interrogated.

---

## P0-2 — Prove the native path actually executes

**2026-09-06T18:37:22Z** — log: `logs/02_native_load.txt`

`native_available()` returning `True` only proves `CDLL` succeeded, so a symbol
was called through `ctypes` in each sprint to prove C++ code really runs:

```
S7  native_available: True
    <CDLL '.../sprint7_battery_testbench/build/libpolaris_bms.so'>
    polaris_ocv_of_soc(0.5) via C++ = 3.7
S8  <CDLL '.../sprint8_flight_test_harness/build/libpolaris_ft.so'>
    ft_wrap_pi(7.0) via C++ = 0.7168146928204138
```

`7.0 − 2π = 0.7168146928204138` ✓. The native path is live in both sprints.

---

## P0-3 — Re-run both suites on the native path

**2026-09-06T18:37:28Z / 18:37:35Z** — logs: `logs/03_pytest_s7_native.txt`,
`logs/04_pytest_s8_native.txt`

| suite | command | result |
|---|---|---|
| S7 | `python -m pytest -ra -q` | **18 passed, 0 failed, 0 skipped**, 2.098 s, exit 0 |
| S8 | `python -m pytest -ra -q` | **28 passed, 0 skipped**, 32.03 s, exit 0 |

S7's count was confirmed via `--junitxml` because the terminal summary line is
not emitted under this configuration:
`{'tests': '18', 'failures': '0', 'errors': '0', 'skipped': '0'}`.

S8's 11 native-parity tests were confirmed to be *collected and executed*, not
skipped: `pytest tests/test_native_parity.py --collect-only` → `11 tests
collected`, and the full run reports 0 skips.

---

## P0-4 — Reproduce the fallback mechanism

**2026-09-06T18:38:51Z** — log: `logs/05_fallback_demo.txt`

The macOS loader condition was reproduced faithfully at the loader level: a
`sitecustomize.py` on `PYTHONPATH` sets `platform.system()` to return
`"Darwin"`, so `_find_library()` searches for `libpolaris_*.dylib` — which the
repository does not contain — exactly as it does on the operator's Mac.

```
platform.system() = Darwin
S7 lib_path         = None
S7 native_available = False
```

Both suites were then run under that condition:

| suite | native loaded | result | exit |
|---|---|---|---|
| S7 | ✗ | **18 passed**, 0 skipped, no warning | 0 |
| S8 | ✗ | **17 passed, 1 skipped** | 0 |

```
SKIPPED [1] tests/test_native_parity.py:25: libpolaris_ft not built (run: cd cpp && make)
```

---

## P0-5 — Native vs pure-Python mirror

`polaris_bms/native.py` states the fallback is *"numerically equivalent to the
C++ core"*. S7 has no test that exercises this, so it was measured directly.

### S7 — probe: `tools/s7_parity_probe.py`, diff: `tools/s7_parity_diff.py`

The same deterministic scenario set was run twice in separate interpreters —
once native, once forced onto the mirror — and the JSON outputs diffed field by
field (`logs/s7_native.json`, `logs/s7_pyfallback.json`,
`logs/06_s7_parity_diff.txt`). Coverage: 21-point OCV sweep; 1C discharge over
600 s at 263.15 / 283.15 / 298.15 / 313.15 K including the full 8-field state
snapshot; all five `Fault` modes at severity 0.7; a 1200-step EKF run started
from a deliberately wrong initial guess (0.50 against a true 0.80).

| section | worst relative deviation | worst absolute |
|---|---|---|
| OCV table | `0.000e+00` | `0.000e+00` |
| cell model (4 temperatures) | `0.000e+00` | `0.000e+00` |
| fault modes (5) | `0.000e+00` | `0.000e+00` |
| EKF | `5.594e-15` (at `rms_err`) | `2.151e-16` |

Fields exceeding a 1e-12 relative tolerance: **0**.

### S8 — probe: `tools/s8_parity_margins.py`, log: `logs/07_s8_parity_margins.txt`

S8's parity tests assert bounds; the measured margins behind those assertions:

| quantity | measured | asserted bound |
|---|---|---|
| single RK4 step, worst abs deviation over 2000 random states | `1.136868e-13` | `< 1e-9` |
| autopilot command, worst abs deviation over 2000 draws | `7.771561e-16` | `< 1e-12` |
| full closed-loop flight, max position divergence (8 scenarios, dt=0.05, seed=3) | `8.20e-13` … `2.57e-12` m | `< 1.0 m` |
| trajectory length delta | `0` ticks, all 8 scenarios | `≤ 2` |
| verdict agreement py/native | identical, all 8 scenarios | required |

The test docstring anticipates "centimetres" of divergence over a multi-km
flight. Measured divergence is ~2.5 picometres — four orders of magnitude
tighter than the tolerance and ten orders tighter than the docstring's
expectation. The tolerance is therefore not exercised by these scenarios.

**Conclusion of P0-5:** on this host and this scenario set, the mirror claim
holds. Results previously obtained on the fallback path are **not numerically
invalidated** — but they were also never *verified*, which is F0-2.

---

## Findings from Phase 0

Each finding below was produced by a command run in this campaign.

### F0-1 — S7's C++ sources are not under version control
**Severity: high (reproducibility).**
```
sprint7_battery_testbench/cpp/cell_model.cpp   untracked (not ignored)
sprint8_flight_test_harness/cpp/flight_core.cpp  TRACKED
```
`.gitignore:8` ignores `build/`, which correctly excludes the compiled
artefacts. But S7's `cpp/` sources themselves are untracked and *not* ignored —
they exist only on this disk. A clone of the repository cannot build
`libpolaris_bms`, so S7's native path is unreproducible by anyone else, and the
sources are one `git clean` away from being lost. S8 does not have this
problem. *Not yet fixed — see Open items.*

### F0-2 — S7's suite has zero coverage of the C++ core
**Severity: high (verification gap).**
`grep -rln native sprint7_battery_testbench/tests/*.py` returns nothing. Under
the simulated Darwin condition S7 runs **18/18 green, exit 0, with no warning
and no skip** (P0-4). The suite is structurally incapable of detecting that the
C++ core is absent, wrong, or stale. S8 has 11 parity tests; S7 has none.
This is the defect that makes the operator's original concern real: a campaign
run on S7 would report success while verifying only the mirror.

### F0-3 — S8's parity skip is one line for eleven tests
**Severity: medium (silent coverage loss).**
`tests/test_native_parity.py:25` calls `pytest.skip(..., allow_module_level=True)`.
When it fires, 11 tests vanish behind a **single** `SKIPPED [1]` line and the
run total drops 28 → 17 with exit code still 0. The mechanism works as
designed — it does not lie — but the report is easy to miss in CI, and it is
one skipped line, not eleven.

### F0-4 — The shipped `libpolaris_bms.so` was not reproducible
**Severity: low (provenance).**
Rebuilding from unchanged sources produced a different binary (P0-1), while two
consecutive rebuilds are byte-identical. S8's library rebuilt byte-for-byte
identical. The S7 artefact on disk was therefore not the product of the current
sources and toolchain. Root cause not established; see the `INFERENCE` note.

### Not a finding — the mirror-equivalence claim holds
P0-5 verified it rather than refuting it. Recorded because it constrains the
severity of F0-2: the gap is *unverified* computation, not *wrong* computation.

---

## Open items leaving Phase 0

| # | Item | Why still open |
|---|---|---|
| O-1 | `libpolaris_bms.dylib` / `libpolaris_ft.dylib` not produced | No macOS shell available to this campaign. The Makefiles' `Darwin` branch (`EXT := dylib`, `LDFLAGS := -dynamiclib`) was read but **not executed**, so it is unverified. |
| O-2 | F0-1 not fixed | Adding S7's `cpp/` to version control is a repository change beyond Phase 0's brief; flagged for decision. |
| O-3 | F0-2 not fixed | Writing S7 parity tests is a code change; deferred pending decision. |
| O-4 | F0-4 root cause | Old toolchain unavailable. Likely to stay unresolved and is low-value to pursue. |

## What Phase 0 does not prove

- Nothing about macOS. The `.dylib` path is untested and the fallback there was
  simulated, not observed.
- Nothing about any sprint other than S7 and S8.
- Nothing about integration. Every result above is a single sprint in
  isolation, which is precisely the condition the rest of this campaign exists
  to break.
- Nothing about real hardware. All inputs are simulator-generated.

---

# Phase 1 — Reproducing the document / code discrepancies of S7 and S8

**2026-09-06, same environment of record as Phase 0** (Linux aarch64, g++ 11.4.0,
CPython 3.10.12, native C++ path loaded and verified). All data remains
synthetic. Logs `10_*` through `23_*`, probes `tools/p1_*.py`.

Five discrepancies were carried into this phase from a static review. All five
reproduced. Execution surfaced two more that the static review had not seen, one
of which is larger than the five.

## Correction to a Phase 0 finding

**F0-1 was overstated and is corrected here.** Phase 0 recorded that S7's `cpp/`
sources are "untracked and not ignored, so the native path is unbuildable from a
clone". The first half is true of the `Polaris_sprint` working copy — where, it
turns out, **the whole of `sprint7_battery_testbench` is untracked**, not just
`cpp/`. The conclusion drawn from it was wrong: in the published repository
(`Polaris`, `origin/main`) S7 including all six `cpp/` files **is** tracked, from
commit `c66d9cb`. A clone can build the native path. What F0-1 actually describes
is a divergence between the scratch copy and the published repository, not a gap
in the published repository. Restated:

> **F0-1 (rev B)** — In the `Polaris_sprint` working copy, `sprint7_battery_testbench`
> is entirely untracked and not gitignored. Changes made there are invisible to
> `git status`, carry no history, and reach the published repository only by manual
> copy. The published repository tracks S7 correctly. Severity: medium (process),
> not high (reproducibility).

The consequence bit during this phase: S7's Phase 1 edits produce no diff in
`Polaris_sprint` and had to be added to the index explicitly.

---

## P1-1 — The committed model no longer produces the committed dataset

Log: `10_p1_s7_campaign.txt`, `11_p1_kcyc_bisect.txt`, `17_p1_krcyc_bisect.txt`,
`16_`/`18_p1_f1-1_fix*.txt`. Probes: `tools/p1_kcyc_bisect.py`,
`tools/p1_krcyc_bisect.py`.

This was not on the list. It was found by doing the first thing the phase asked
for — running the script FA-001 says produces its numbers.

```
python3 scripts/run_cycling_campaign.py
```

| | shipped `data/` | this run |
|---|---|---|
| HEALTHY final SoH | 97.745 % | **93.318 %** |
| LITHIUM_PLATING final SoH | 94.329 % | **83.077 %** |
| RUL, LITHIUM_PLATING | 337 | **80** |
| RUL, HEALTHY | 924 | **279** |

Every figure in FA-001 derives from that dataset, so the report described a model
that was no longer in the repository.

The discrepancy is not random and not a backend artefact: the loss ratio is a
constant 2.96 from the first cycle onward, which is the signature of a single
scaled coefficient. Bisecting the cycle-fade coefficient on the pure-Python
backend (`tools/p1_kcyc_bisect.py`) located it:

```
   k_cyc  scenario            soh[1]   soh[60]   shipped soh[1] shipped soh[60]   max |err|
  0.0090  HEALTHY             99.126    93.318           99.705          97.745      4.4268
  0.0030  HEALTHY             99.705    97.745           99.705          97.745      0.0000   <== MATCH
  0.0030  LITHIUM_PLATING     99.259    94.329           99.259          94.329      0.0001   <== MATCH
```

Restoring `k_cyc = 0.0030` reproduced the SoH trace exactly but left the
impedance-derived features 3–7 % off (`ir_drop_v`, `peak_charge_dvdq`). The same
bisection on the resistance-growth coefficient (`tools/p1_krcyc_bisect.py`)
closed it:

```
   0.0020  HEALTHY             0.0766    0.0743    87.554    84.921      3.10e-02
   0.0008  HEALTHY             0.0743    0.0743    84.921    84.921      3.73e-16   <== MATCH
   0.0008  LITHIUM_PLATING     0.1127    0.1127    56.223    56.223      1.52e-15   <== MATCH
```

**Fix applied.** `cpp/cell_model.hpp` and the Python mirror in
`polaris_bms/native.py`: `k_cyc 0.0090 → 0.0030`, `k_r_cyc 0.0020 → 0.0008`.
S7 rebuilt, campaign re-run:

```
cycle_records.json  : BYTE-IDENTICAL to shipped
rul_projections.json: BYTE-IDENTICAL to shipped
Triage in-sample accuracy: 279/295 = 94.6%
```

Three independent confirmations that these are the generating values: the raw
dataset is byte-identical, the RUL file is byte-identical, and the in-sample
triage accuracy returns to **94.6 %**, the number FA-001 §6 has always quoted and
which the drifted model could not produce (it gave 92.5 %, then 94.2 % after only
the first coefficient was restored).

Native and pure-Python mirror re-verified after the change: worst relative
deviation 6.7e-15, zero fields outside 1e-12.

**Which was wrong: the code.** The dataset, the RUL file and the report agreed
with each other and disagreed only with the source. Decided in consultation with
the operator; the alternative (regenerate everything against `0.0090`) would have
invalidated every published S7 figure to no benefit, since neither value is
traceable to a physical calibration.

**Test that locks it:** `tests/test_dataset_reproducibility.py::test_committed_dataset_is_reproducible`,
parametrised over all five scenarios, pins seven features per cycle against the
committed dataset at `rel=1e-9`. Verified to fail on the pre-fix code — see
`22_p1_tests_fail_prefix.txt`, 5 failures — and to pass after.

## P1-2 — FA-001 campaign temperature (was on the list)

`scripts/run_cycling_campaign.py:28` configures `LITHIUM_PLATING` at **283.15 K**
(+10 °C). FA-001 §1 said **−10 °C (263.15 K)**.

Reproduced, and settled by more than reading the table: the shipped dataset is
reproduced byte-for-byte by a run at 283.15 K (P1-1). The campaign that produced
FA-001 was run at +10 °C. The model's plating mechanism triggers below 15 °C
(FA-001 §6), so 283.15 K is inside the plating regime and the code is
self-consistent.

**Which was wrong: the report.** Corrected to +10 °C (283.15 K), with the change
recorded in a new §0 revision notice rather than silently. If −10 °C was the
intended test point, that is a re-run of the campaign and a full regeneration of
`data/`, not a text edit — left as an operator decision.

## P1-3 — FA-001 bootstrap confidence interval (was on the list)

FA-001 §3 cited a "1000-sample bootstrap of the regression slope: 5th / 95th
percentile = 335 / 342".

```
grep -rni "bootstrap" . --include=*.py --include=*.md --include=*.json --include=*.sh
./reports/FA-001_lithium_plating_signature.md:33:  ... 1000-sample bootstrap ...
```

The only occurrence in the sprint is the claim itself. `rul_projection`
(`polaris_bms/triage.py:104-119`) is a bare `np.polyfit` degree 1 with no
resampling and no uncertainty output.

**Which was wrong: the report.** The interval could not have been produced by
this repository. It was **withdrawn**, not recomputed: implementing a bootstrap
to retro-fit a published number would be inventing the evidence a second time,
and adding an estimator is a feature, not a defect fix. §3 now states plainly
that no interval is quoted because the code computes none.

## P1-4 — FA-001 RUL 339 vs 337 (was on the list)

Recomputing `rul_projection` on the shipped records:

```
scenario                  recomputed  stored json  FA-001 text
HEALTHY                          924          924          924
LITHIUM_PLATING                  337          337          339
SEI_GROWTH                       480          480            -
```

The code, the stored JSON and the report agree everywhere except this one cell.

**Which was wrong: the report.** Corrected to 337.

## P1-5 — FA-002 root cause (was on the list, and worse than suspected)

Logs: `13_`, `14_`, `19_p1_*`. Probe: `tools/p1_fa002_clip.py`.

`scripts/benchmark_estimators.py:62` read

```python
init_guess = float(np.clip(true_init - guess_err, 0.05, 0.95))
```

with every scenario starting the cell at `soc0 = 1.0`. The **upper** bound
therefore seeded all three estimators at 0.95 against a true 1.00 whenever
`guess_err` was small — including `baseline_25c`, whose own table row declares a
guess error of 0.0.

Measured, clip on versus clip removed, nothing else changed:

```
baseline, no bias at all, clip ON  : CC rms = 0.0496   <- pure artefact, zero bias applied
baseline, no bias at all, clip OFF : CC rms = 0.0005
biased shunt (0.08 A), clip ON     : CC rms = 0.0761   <- the 0.076 quoted in FA-002
biased shunt (0.08 A), clip OFF    : CC rms = 0.0285   <- what the shunt bias alone costs
```

FA-002 §3 attributed 0.05 to the shunt bias and "the additional 0.026" to a wrong
initial guess the scenario did not declare. The two terms are real and sum
correctly, but **they are the wrong way round**: the seed artefact is the larger
term (0.0496), the shunt bias the smaller (0.0285).

The consequence is larger than a misattributed sentence. Open-loop coulomb
counting cannot recover from a seed error; the EKF re-anchors on voltage within
seconds. The gap between them was measuring the size of the injected handicap.

**Fix applied,** guard widened to the physical range `(0.0, 1.0)`, extracted into
a documented `seed_guess()` so it can be tested, and the campaign re-run:

| scenario | CC before | CC after | EKF before | EKF after | EKF advantage before → after |
|---|---|---|---|---|---|
| baseline_25c | 0.0498 | **0.0002** | 0.0016 | 0.0003 | +96.9 % → **−9.7 %** |
| bad_guess_25c | 0.3998 | 0.3998 | 0.0053 | 0.0053 | +98.7 % → +98.7 % |
| biased_shunt_25c | 0.0763 | **0.0287** | 0.0105 | **0.0575** | +86.3 % → **−100.0 %** |
| biased_and_bad_guess | 0.4252 | 0.4252 | 0.0100 | 0.0100 | +97.7 % → +97.7 % |
| cold_minus_10c | 0.2125 | 0.2125 | 0.0546 | 0.0546 | +74.3 % → +74.3 % |
| hot_plus_45c | 0.2125 | 0.2125 | 0.0286 | 0.0286 | +86.6 % → +86.6 % |

Only the two scenarios that were supposed to be clean moved. The three with a
large declared guess error are untouched, because there the injected 0.05 was
swamped by the declared 0.4 or 0.2. That selectivity is itself the signature of a
seeding defect rather than a modelling change.

**FA-002's headline is withdrawn.** "90 % on average" becomes: decisive on seed
error (+98.7 %, +97.7 %), solid at temperature extremes (+74.3 %, +86.6 %), no
help on a clean run, and **twice as bad as open-loop counting under a pure shunt
bias with a correct seed** (0.0575 vs 0.0287). No average is quoted in rev B,
because averaging percentages across scenarios whose baseline error spans 0.0002
to 0.4252 is dominated by near-zero denominators.

Partial root cause for the last row, supportable from the code: the EKF's state
vector is `[SOC, v_rc1, v_rc2]` — there is **no current-bias state**, so a DC
shunt offset is not observable to the filter. Why it ends up *worse* than the
counter rather than merely equal is **not established** and is left open below.

**Which was wrong: both.** The code had a real defect; the report both
misattributed it and built its headline on it. Both corrected, with FA-002 rev B
carrying an explicit withdrawal notice rather than a quiet renumbering.

**Test that locks it:** `test_seed_guard_does_not_invent_a_guess_error`. Verified
to fail on the pre-fix code (`assert 0.95 == 1.0`) and pass after.

## P1-6 — FA-001 cluster posterior (not on the list)

FA-001 §1 claimed a "mean cluster posterior of 0.93" over the plating cycles.
Recomputed on the restored, byte-identical dataset:

```
LITHIUM_PLATING correctly triaged: 58/59   (FA-001 says 58 / 59)          OK
mean cluster posterior on those cycles: 1.0000   (FA-001 says 0.93)       WRONG
overall in-sample accuracy: 279/295 = 94.6%   (FA-001 says 94.6 %)        OK
```

**Which was wrong: the report** — and the truth is less flattering than the
claim. Every posterior is exactly 1.000: eight clusters over 295 points drawn
from five deterministic trajectories separate so cleanly that the GMM saturates.
The posterior carries no confidence information at all and must not be presented
as one. FA-001 §6 now says so.

## P1-7 — S8 README, thrust_loss row (was on the list)

```
python scripts/run_campaign.py --seeds 4 --dt 0.05 --outdir /tmp/s8_camp

scenario            pass   xt_rms  xt_max alt_rms  Va_rms navRMSE
nominal            4/4       1.23   15.07    2.22    0.80    1.51
thrust_loss        0/4       1.15   10.00    1.79    2.01    1.55
```

The README's `thrust_loss` row read `1.24 | 15.1` — within rounding of the
nominal row's `1.23 | 15.1`. Actual values are **1.15 / 10.00**. Every other cell
in that table, all seven other scenarios and all five other columns, reproduces
exactly as printed.

**Which was wrong: the README.** Corrected in place with a dated footnote. The
error direction matters: it made a thrust-loss failure look like it tracked
cross-track no better than nominal, when it actually tracks noticeably tighter.

---

## Phase 1 regression status

```
S7: {'tests': '25', 'failures': '0', 'errors': '0', 'skipped': '0', 'time': '3.814'}
S8: {'tests': '28', 'failures': '0', 'errors': '0', 'skipped': '0', 'time': '32.592'}
```

S7 was 18 tests before this phase and is 25 after (7 added, all locking a fix).
No pre-existing test changed behaviour. `data/cycle_records.json` and
`data/rul_projections.json` are byte-identical to what they were on entry;
`data/estimator_benchmark.{json,csv}` are regenerated, which is the point of P1-5.

## Open after Phase 1

| # | Item | Why open |
|---|---|---|
| O-5 | The EKF is worse than open-loop counting under pure shunt bias with a correct seed (0.0575 vs 0.0287) | Reproduced and reported, root cause not established. Adding a current-bias state is a design change, deliberately not made. |
| O-6 | `baseline_25c` now seeds the estimators with the exact true SOC | Physically unrealistic, but it is what a declared guess error of 0.0 means. Starting the cell at `soc0 = 0.9` would fix the design; that is a change to the experiment, not a defect fix. |
| O-7 | Neither `k_cyc = 0.0030` nor `k_r_cyc = 0.0008` is traceable to a physical calibration | The header calls them "calibrated for accelerated test cycling" with no source. Restored to the generating values because reproducibility was the defect; the values themselves remain unjustified. |
| O-8 | FA-001 was written for −10 °C but the campaign ran at +10 °C | The report was corrected to match what ran. Whether +10 °C is the test point that was actually wanted is an operator decision, and changing it means regenerating `data/`. |
| O-1..O-4 | carried forward from Phase 0 | unchanged |

## What Phase 1 does not prove

- Nothing about S9, S10 or S12, and nothing about integration. Every check above
  is still a single sprint in isolation.
- Nothing about whether the model is *right*. P1-1 restored the code to the
  values that generate the shipped data; it did not validate either value against
  a real cell, and no such validation is possible with synthetic data.
- Nothing about held-out triage performance. The 94.6 % remains in-sample, and
  P1-6 shows the posteriors that would normally qualify it are degenerate.
