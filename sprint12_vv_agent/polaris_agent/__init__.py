"""Polaris Sprint 12 — Agentic V&V Analyst.

An autonomous analyst that performs the workflow a certification / V&V
engineer does by hand: read the graded evidence produced by Sprints 7-11,
decide which analysis tools to run, run them, reason over the results, and
write a certification *findings report* with root-cause hypotheses and
recommendations.

Two things make this a V&V tool rather than a chatbot:

  1. **The agent has no way to produce a number.** Every figure that reaches
     the report comes from a deterministic tool observation grounded in the
     Sprint 7-11 artefacts (via Sprint 10's `polaris_fc` grading layer). The
     language model — when enabled — only *selects which tool to call*. It
     cannot type a metric into the report; it can only cite a requirement ID,
     and the report binds the grounded value. This is the anti-hallucination
     guarantee (see MODEL.md).

  2. **The reasoning policy is swappable.** The exact same tool layer is
     driven either by a `DeterministicPolicy` (rule-based, no network, so
     `verify.py` reproduces every number) or an `LLMPolicy` (Anthropic
     tool-use, enabled with --live). The agent loop does not know or care
     which one it is talking to.
"""
from .tools import (
    ToolSpec, ToolRegistry, ToolContext, build_registry,
)
from .agent import (
    Agent, AgentResult, Policy, DeterministicPolicy, LLMPolicy,
    Step, Action,
)
from .report import render_findings_report

__all__ = [
    "ToolSpec", "ToolRegistry", "ToolContext", "build_registry",
    "Agent", "AgentResult", "Policy", "DeterministicPolicy", "LLMPolicy",
    "Step", "Action", "render_findings_report",
]

__version__ = "1.0.0"
