"""Run the Agentic V&V Analyst and write a certification findings report.

Examples
--------
    # Deterministic (default) — no API key, fully reproducible:
    python scripts/run_agent.py

    # One subsystem only:
    python scripts/run_agent.py --subsystem BATTERY_PACK

    # Live LLM reasoning (needs `pip install anthropic` + ANTHROPIC_API_KEY):
    python scripts/run_agent.py --live

The numbers in the report are identical either way — only the reasoning path
differs. See MODEL.md for why.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from polaris_agent import (                                   # noqa: E402
    Agent, DeterministicPolicy, LLMPolicy, build_registry,
    render_findings_report,
)
from polaris_agent.tools import Subsystem                     # noqa: E402


def _print_step(step) -> None:
    print(step.as_text())


def main() -> int:
    ap = argparse.ArgumentParser(description="Polaris Agentic V&V Analyst")
    ap.add_argument("--subsystem", action="append",
                    choices=[s.value for s in Subsystem],
                    help="Restrict to one or more subsystems "
                         "(repeatable). Default: all.")
    ap.add_argument("--basis", default="baseline",
                    help="Acceptance basis to grade against: 'baseline' "
                         "(ratified, fleet passes) or 'stress' (tightened, "
                         "surfaces findings). Default: baseline.")
    ap.add_argument("--live", action="store_true",
                    help="Use the Anthropic LLM policy instead of the "
                         "deterministic one (needs ANTHROPIC_API_KEY).")
    ap.add_argument("--model", default="claude-sonnet-5",
                    help="Model for --live (default: claude-sonnet-5).")
    ap.add_argument("--out", default=None,
                    help="Report path. Default: reports/findings_<date>.md")
    ap.add_argument("--no-transcript", action="store_true",
                    help="Omit the reasoning transcript from the report.")
    ap.add_argument("--quiet", action="store_true",
                    help="Do not stream steps to stdout.")
    args = ap.parse_args()

    registry = build_registry(basis=args.basis)

    if args.live:
        policy = LLMPolicy(model=args.model)
        goal = (
            f"Investigate the certification evidence (acceptance basis: "
            f"{args.basis}) for "
            + (", ".join(args.subsystem) if args.subsystem
               else "all subsystems")
            + " and produce findings. Follow the analyst procedure exactly.")
    else:
        policy = DeterministicPolicy(subsystems=args.subsystem)
        goal = ("Produce the certification findings for "
                + (", ".join(args.subsystem) if args.subsystem
                   else "the whole fleet") + ".")

    print(f"=== Agentic V&V Analyst ===")
    print(f"policy : {policy.name}")
    print(f"basis  : {args.basis}")
    print(f"goal   : {goal}")
    print()

    agent = Agent(registry=registry, policy=policy,
                  on_step=None if args.quiet else _print_step)
    result = agent.run(goal)

    print()
    print(f"stopped: {result.stopped_reason} after {result.n_steps} steps, "
          f"{result.ctx.tool_calls} tool calls, "
          f"{len(result.ctx.findings)} finding(s).")

    report = render_findings_report(
        result, include_transcript=not args.no_transcript)

    out_dir = HERE.parent / "reports"
    out_dir.mkdir(exist_ok=True)
    if args.out:
        out_path = Path(args.out)
    else:
        from datetime import datetime, timezone
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        out_path = out_dir / f"findings_{stamp}.md"
    out_path.write_text(report)
    print(f"report : {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
