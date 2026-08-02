"""The agent loop and its two interchangeable reasoning policies.

The loop is a classic ReAct / tool-use cycle:

    observe state -> policy picks an Action -> execute tool -> record Step -> repeat

It is deliberately thin. It owns *control* (termination, the step budget, the
tool allow-list, transcript keeping) but delegates every *decision* to a
`Policy`. That separation is the whole point: the identical tool layer is
driven either by a rule-based `DeterministicPolicy` (no network, reproducible)
or an `LLMPolicy` (Anthropic tool-use). Swapping them changes nothing about
how evidence is read or how the report is built.

Guardrails (see MODEL.md):
  * hard step budget                     -> no runaway loops
  * tool allow-list via the registry     -> closed action space
  * every observation is grounded         -> the policy cannot inject a number
  * finalize() is the only clean exit     -> a report always has a decision
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .tools import ToolContext, ToolRegistry


# --- Transcript types ---------------------------------------------------------

@dataclass
class Action:
    tool: str
    arguments: Dict[str, Any]
    thought: str = ""


@dataclass
class Step:
    index: int
    thought: str
    tool: str
    arguments: Dict[str, Any]
    observation: Any
    error: Optional[str] = None

    def as_text(self) -> str:
        obs = self.error or json.dumps(self.observation, default=str)
        if len(obs) > 700:
            obs = obs[:700] + " …"
        head = f"[{self.index}] {self.tool}({json.dumps(self.arguments, default=str)})"
        thought = f"\n     ↳ thought: {self.thought}" if self.thought else ""
        return f"{head}{thought}\n     ↳ obs: {obs}"


@dataclass
class AgentResult:
    goal: str
    transcript: List[Step]
    ctx: ToolContext
    policy_name: str
    stopped_reason: str

    @property
    def n_steps(self) -> int:
        return len(self.transcript)


# --- Policy interface ---------------------------------------------------------

class Policy(Protocol):
    name: str

    def decide(self, goal: str, registry: ToolRegistry,
               transcript: List[Step]) -> Action:
        """Return the next Action given the goal and history so far."""
        ...


# --- Deterministic policy -----------------------------------------------------

class DeterministicPolicy:
    """A rule-based V&V analyst.

    Encodes the fixed procedure a methodical engineer would follow, so the
    run is byte-for-byte reproducible and needs no API key:

        1. survey subsystems
        2. grade each target subsystem
        3. for every FAILing requirement: inspect its triage cluster, pull
           provenance, and record a finding with a cause/recommendation
           chosen from the requirement's own metadata
        4. finalize with a go/no-go rationale

    The decision of *what to look at next* is made purely from the transcript
    so the same logic slots into the same loop the LLM policy uses.
    """
    name = "deterministic"

    def __init__(self, subsystems: Optional[List[str]] = None):
        self._targets = subsystems      # None => discover from list_subsystems
        self._plan: List[Action] = []
        self._planned = False

    # -- root-cause / recommendation heuristics, keyed by requirement family --
    _CAUSE = {
        "FC-BAT-001": ("EKF SOC-RMS exceeds bound in the cold-temperature "
                       "characterisation regime; low-temperature impedance rise "
                       "degrades the observer's voltage model.",
                       "Accept as a tracked MAJOR finding: gain-schedule the EKF "
                       "R/Q by temperature, or restrict the usable-range guarantee "
                       "below the cold cut-off. Re-test HPPC at the cold set-point."),
        "FC-UAV": ("Closed-loop mission missed a flight-test card under the "
                   "injected fault; the navigation EKF/control authority margin "
                   "is insufficient for this scenario.",
                   "Review the failing test card's tolerance and the fault "
                   "magnitude; add a mitigation or a documented flight envelope "
                   "restriction, then re-run the campaign."),
        "FC-LDG-001": ("Nominal touchdown dispersion (Monte-Carlo CEP) exceeds "
                       "the tightened pad acceptance radius; the vision/GPS "
                       "guidance is accurate but not to the stricter radius.",
                       "Either accept the wider radius as the certified pad "
                       "spec, or reduce dispersion (tighter fiducial-lock gate, "
                       "later GPS→vision handover) and re-run the dispersion "
                       "campaign to confirm CEP under the new radius."),
        "FC-LDG": ("Approach did not touch down inside tolerance / did not "
                   "correctly reject an unsafe final.",
                   "Tune the decision-height go-around gate or the GPS→vision "
                   "handover; re-run the Monte-Carlo dispersion campaign."),
        "FC-BAT": ("Battery pack requirement not met on the graded evidence.",
                   "Open a MAJOR finding; determine whether the fade model or the "
                   "triage labelling is the driver, then re-characterise."),
    }

    def _disposition_for(self, view: Dict[str, Any]) -> str:
        if view.get("blocking"):
            return "BLOCKER"
        if view.get("severity") == "MAJOR":
            return "WAIVER_CANDIDATE"
        return "FINDING"

    def _cause_for(self, req_id: str) -> tuple[str, str]:
        for key in (req_id, req_id.rsplit("-", 1)[0]):
            if key in self._CAUSE:
                return self._CAUSE[key]
        return ("Requirement not met on the graded evidence.",
                "Open a finding and investigate the responsible campaign.")

    def _build_plan(self, registry: ToolRegistry) -> None:
        """Grade the targets once, then lay out the full action sequence."""
        ctx = registry.ctx
        roll = ctx.rollup()
        targets = self._targets or [s.value for s in roll.by_subsystem]

        plan: List[Action] = [Action("list_subsystems", {},
                                     "Survey the fleet before drilling in.")]
        for sub in targets:
            plan.append(Action("grade_requirements", {"subsystem": sub},
                               f"Grade every requirement for {sub}."))
        # Determine failing requirements from the basis-aware grading.
        failing = [r for r in ctx.failing()
                   if (not self._targets or
                       r.requirement.subsystem.value in targets)]
        for r in failing:
            rid = r.requirement.id
            plan.append(Action("inspect_anomaly_triage", {"requirement_id": rid},
                               f"Find the root-cause cluster behind {rid}."))
            plan.append(Action("get_evidence_provenance", {"requirement_id": rid},
                               f"Capture the audit trail for {rid}."))
            cause, rec = self._cause_for(rid)
            view = {"blocking": ctx.is_blocking(r),
                    "severity": r.requirement.severity.value}
            plan.append(Action(
                "record_finding",
                {"requirement_id": rid, "root_cause": cause,
                 "recommendation": rec,
                 "disposition": self._disposition_for(view)},
                f"Disposition {rid}."))

        n_fail = len(failing)
        if n_fail == 0:
            rationale = ("All graded requirements pass across the targeted "
                         "subsystems; recommend GO. No blocking findings; "
                         "evidence hashes recorded for the certification file.")
        else:
            n_block = sum(1 for r in failing if ctx.is_blocking(r))
            verdict = "NO-GO" if n_block else "GO WITH FINDINGS"
            rationale = (
                f"{n_fail} requirement(s) failed ({n_block} blocking); "
                f"recommend {verdict}. Each failure is dispositioned with a "
                f"root-cause hypothesis and a recommendation; blocking items "
                f"must clear before certification.")
        plan.append(Action("finalize", {"decision_rationale": rationale},
                           "Emit the go/no-go decision basis."))
        self._plan = plan
        self._planned = True

    def decide(self, goal: str, registry: ToolRegistry,
               transcript: List[Step]) -> Action:
        if not self._planned:
            self._build_plan(registry)
        idx = len(transcript)
        if idx < len(self._plan):
            return self._plan[idx]
        # Safety: if somehow over-run, finalize.
        return Action("finalize",
                      {"decision_rationale": "Investigation complete."},
                      "Terminate.")


# --- LLM policy (optional, --live) --------------------------------------------

_SYSTEM_PROMPT = """\
You are a certification / V&V analyst for an aerospace fleet. You investigate \
the graded evidence for the requested subsystem(s) using ONLY the provided \
tools, then produce findings.

Rules you must follow:
- You cannot know any measurement except by calling a tool. Never state or \
guess a number; cite requirement IDs and let the report bind the values.
- Procedure: survey subsystems, grade the target subsystem(s), and for EVERY \
failing requirement call inspect_anomaly_triage and get_evidence_provenance, \
then record_finding with a concise physical root cause and a concrete \
recommendation.
- Do not record findings against passing requirements.
- When every failing requirement has a recorded finding, call finalize once \
with a short go/no-go rationale. Then stop.
Think briefly before each tool call."""


class LLMPolicy:
    """Drives the same tool layer with the Anthropic tool-use API.

    Requires the `anthropic` package and ANTHROPIC_API_KEY. Enabled with
    --live. The model only *chooses tools*; it never supplies evidence
    numbers, so switching the policy on cannot change any figure in the
    report — only the path taken to discover the findings.
    """
    name = "llm"

    def __init__(self, model: str = "claude-sonnet-5",
                 max_tokens: int = 1024):
        try:
            import anthropic          # noqa: F401
        except ImportError as e:      # pragma: no cover - env dependent
            raise RuntimeError(
                "LLMPolicy needs the 'anthropic' package: "
                "pip install anthropic --break-system-packages") from e
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "LLMPolicy needs ANTHROPIC_API_KEY in the environment.")
        from anthropic import Anthropic
        self._client = Anthropic()
        self._model = model
        self._max_tokens = max_tokens
        self._messages: List[Dict[str, Any]] = []
        self._pending_tool_use_id: Optional[str] = None
        self._primed = False

    def _prime(self, goal: str) -> None:
        self._messages = [{"role": "user", "content": goal}]
        self._primed = True

    def _sync_last_observation(self, transcript: List[Step]) -> None:
        """Feed the previous tool result back to the model."""
        if not transcript or self._pending_tool_use_id is None:
            return
        last = transcript[-1]
        payload = last.error or json.dumps(last.observation, default=str)
        self._messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": self._pending_tool_use_id,
                "content": payload,
                "is_error": last.error is not None,
            }],
        })
        self._pending_tool_use_id = None

    def decide(self, goal: str, registry: ToolRegistry,
               transcript: List[Step]) -> Action:
        if not self._primed:
            self._prime(goal)
        self._sync_last_observation(transcript)

        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=_SYSTEM_PROMPT,
            tools=registry.anthropic_schema(),
            messages=self._messages,
        )
        self._messages.append({"role": "assistant", "content": resp.content})

        thought_parts, tool_use = [], None
        for block in resp.content:
            if block.type == "text":
                thought_parts.append(block.text)
            elif block.type == "tool_use":
                tool_use = block
        thought = " ".join(t.strip() for t in thought_parts if t.strip())

        if tool_use is None:
            # Model chose to stop talking without a tool — end cleanly.
            return Action("finalize",
                          {"decision_rationale": thought or "Complete."},
                          thought)
        self._pending_tool_use_id = tool_use.id
        return Action(tool_use.name, dict(tool_use.input or {}), thought)


# --- The loop -----------------------------------------------------------------

@dataclass
class Agent:
    registry: ToolRegistry
    policy: Policy
    max_steps: int = 40
    on_step: Optional[Any] = None       # callable(Step) -> None, for live print

    def run(self, goal: str) -> AgentResult:
        transcript: List[Step] = []
        stopped = "max_steps"
        for i in range(self.max_steps):
            action = self.policy.decide(goal, self.registry, transcript)
            error: Optional[str] = None
            observation: Any = None
            try:
                observation = self.registry.call(action.tool, action.arguments)
            except Exception as e:                      # tool-level error
                error = f"{type(e).__name__}: {e}"
            step = Step(index=i, thought=action.thought, tool=action.tool,
                        arguments=action.arguments, observation=observation,
                        error=error)
            transcript.append(step)
            if self.on_step:
                self.on_step(step)
            if action.tool == "finalize" and error is None:
                stopped = "finalized"
                break
        return AgentResult(goal=goal, transcript=transcript,
                           ctx=self.registry.ctx, policy_name=self.policy.name,
                           stopped_reason=stopped)
