# MODEL.md — Agentic V&V Analyst: architecture, guarantees, and design choices

This document explains *how* the agent is built and *why* it is built that
way. The central idea: an agent that is trustworthy for a verification task
must have no way to fabricate a result. Everything below serves that.

## 1. The loop (ReAct / tool-use)

The agent runs the classic observe → decide → act cycle:

```
for step in range(max_steps):
    action = policy.decide(goal, registry, transcript)   # DECIDE
    observation = registry.call(action.tool, action.args) # ACT (grounded)
    transcript.append(Step(..., observation, error))      # OBSERVE
    if action.tool == "finalize": break                   # TERMINATE
```

`agent.py::Agent.run` owns *control only*: the step budget, the tool
allow-list (via the registry), transcript keeping, per-tool error capture, and
termination. It contains no domain logic and no knowledge of the evidence. All
*decisions* are delegated to a `Policy`.

## 2. The Policy interface (swappable reasoning)

```python
class Policy(Protocol):
    name: str
    def decide(self, goal, registry, transcript) -> Action: ...
```

Two implementations drive the **identical** tool layer:

- **`DeterministicPolicy`** — a rule-based analyst. On first call it grades the
  targets once and lays out the full action sequence a methodical engineer
  would follow: survey subsystems → grade each target → for every failing
  requirement, inspect its anomaly cluster, pull provenance, and record a
  finding whose disposition (FINDING / WAIVER_CANDIDATE / BLOCKER) is derived
  from the requirement's severity and blocking status → finalize with a
  go/no-go rationale. It reads only the transcript to know where it is, so it
  slots into the same loop the LLM uses. No network; byte-for-byte
  reproducible.

- **`LLMPolicy`** — sends the goal, the tool schemas, and the running message
  history to the Anthropic tool-use API and returns whatever tool the model
  picks. Enabled with `--live`; needs the `anthropic` package and
  `ANTHROPIC_API_KEY`. Fails fast with a clear message if either is missing.

Because the loop cannot distinguish the two, the LLM is a *drop-in reasoning
backend*, not a special path. This is the cleanest way to show an agent
architecture: the intelligence is pluggable and the scaffolding is dumb.

## 3. The tool registry is the entire action space

`tools.py` exposes exactly nine tools, each a `ToolSpec(name, description,
parameters, func)` where `parameters` is a JSON schema and `func` is a
deterministic Python callable. `ToolSpec.to_anthropic()` renders the schema
in the API's `input_schema` shape, so the same registry serves both policies.

`ToolRegistry.call` is the single choke point:

- it rejects any name not in the allow-list (`KeyError`), so the model cannot
  invent capabilities;
- it counts calls (surfaced in the report header);
- there is no eval/shell/compute-expression tool, by design — the agent's
  reach is closed over grounded operations.

Read tools: `list_subsystems`, `list_requirements`, `grade_requirements`,
`get_failing_requirements`, `inspect_anomaly_triage`,
`get_evidence_provenance`, `list_fault_injections`. Write/control tools:
`record_finding` (mutates state), `finalize` (the only clean exit).

## 4. Grounding — why the agent can't hallucinate a number

Two mechanisms combine:

1. **Every observation is grounded.** All read tools ultimately call Sprint
   10's `polaris_fc.build_evidence`, which reads the versioned Sprint 7–11
   JSON artefacts and grades them. The agent never receives a number that
   didn't come from a checked-in artefact through a fixed grading rule.

2. **The report re-binds numbers from evidence, not from the agent.** A
   `record_finding` call accepts only `requirement_id`, `root_cause`,
   `recommendation`, `disposition` — deliberately no numeric fields, and it is
   rejected outright if the cited requirement passed. At render time,
   `report.py` looks up each finding's requirement in the graded roll-up and
   binds the measured value, bound, evidence hash, and anomaly cluster from
   *there*. So a finding's prose can be wrong, but the quantitative columns of
   the report are structurally guaranteed to be the real graded values.
   (`tests/test_report.py::test_numbers_come_from_evidence_not_findings`
   injects a lie into a finding and asserts it never reaches the criterion
   line.)

Consequence: switching `--live` on cannot change any figure in the report. The
model influences *which findings are discovered and how they're explained*,
never *what the data says*.

## 5. Acceptance basis vs. measurement

A subtle but important separation:

- **Measurement** = what the Sprint 7–11 evidence records. Fixed.
- **Acceptance basis** = the thresholds a measurement is graded against.
  Selectable (`baseline` | `stress`).

`ToolContext` applies a basis as a map `requirement_id -> tightened_bound` and
recomputes PASS/FAIL, blocking status, subsystem and fleet status, and the
per-run "worst run" against the effective bound (using `polaris_fc`'s own
`_op_check`, so grading semantics stay identical). `baseline` has an empty
override map and reproduces Sprint 10 exactly. `stress` tightens two bounds to
exercise the findings path. `test_measurements_are_basis_invariant` locks in
that a basis change moves the verdict but never the value.

This mirrors real certification: the same test data is re-adjudicated when the
acceptance criteria tighten (a stricter customer spec, a new reg). The report
always prints the basis and shows the original catalog bound beside any
tightened one, so a reader can never mistake a hypothetical for a defect.

## 6. Guardrails, summarised

| Risk | Guardrail |
|---|---|
| Runaway loop | hard `max_steps` budget (default 40); loop breaks on `finalize` |
| Capability escape | closed tool allow-list enforced in `ToolRegistry.call` |
| Fabricated metric | numbers bound from evidence by id, never from the agent |
| Finding on good evidence | `record_finding` rejects passing requirements |
| Report with no decision | `finalize` is the only clean exit; a decision always exists |
| Silent tool failure | every tool error is captured into the transcript and surfaced |

## 7. What this is not

- Not a simulator — it does not re-run any physics; it adjudicates existing
  evidence. (`list_fault_injections` exposes the re-runnable campaigns as
  metadata but the analyst loop does not execute them.)
- Not a general chatbot — the action space is nine grounded tools.
- Not a claim of real hardware — the underlying evidence is synthetic, as in
  Sprints 7–11.

---

*Engineering clarity for complex futures.*
