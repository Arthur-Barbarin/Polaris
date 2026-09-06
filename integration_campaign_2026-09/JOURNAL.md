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
