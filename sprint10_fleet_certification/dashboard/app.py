"""Streamlit — Fleet Certification Console.

Tabs:
  Overview         fleet-level roll-up (subsystem status, blocking findings)
  Traceability     the full requirement -> test card -> evidence table
  Requirement      drill-in on one requirement (per-run evidence, triage cluster)
  Inject Fault     re-run a source-sprint campaign, watch the matrix move
  Provenance       artefact manifest + sha-256 hashes + evidence-package export
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

# Make the package importable when Streamlit is launched from anywhere.
HERE = Path(__file__).resolve().parent
REPO_SPRINT = HERE.parent
sys.path.insert(0, str(REPO_SPRINT))

from polaris_fc import (  # noqa: E402
    REQUIREMENTS, Requirement, Severity, Subsystem,
    build_evidence, run_summary,
)
from polaris_fc.inject import (  # noqa: E402
    available_injections, run_injection,
)


def repo_root() -> Path:
    # sprint10 sits inside Polaris_sprint/; the sibling sprints are at repo_root.
    return REPO_SPRINT.parent


STATUS_COLOR = {
    "GREEN": "#22c55e", "FINDINGS": "#f59e0b",
    "BLOCKED": "#ef4444", "NO_EVIDENCE": "#94a3b8",
}
PASS_ICON = {True: "✅", False: "❌"}


def _badge(text: str, color: str) -> str:
    return (f"<span style='background:{color};color:white;padding:2px 8px;"
            f"border-radius:6px;font-size:0.85em;font-weight:600;'>{text}</span>")


def _requirement_df(res) -> pd.DataFrame:
    rows = []
    for r in res.all_results():
        req: Requirement = r.requirement
        rows.append({
            "ID": req.id,
            "Subsystem": req.subsystem.value,
            "Requirement": req.title,
            "Op": req.op,
            "Bound": req.bound,
            "Value": r.aggregated_value,
            "N runs": r.n_runs_considered,
            "Status": r.status,
            "Severity": req.severity.value,
            "Artefact hash": r.artefact_hash,
        })
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ page setup
st.set_page_config(page_title="Polaris — Fleet Certification Console",
                   layout="wide", page_icon="✈️")
st.title("Polaris — Fleet Certification Console")
st.caption(
    "Cross-subsystem traceability over sprints 7 (battery), 8 (fixed-wing "
    "UAV), 9 (precision landing). Every claim on this page is a numeric "
    "comparison against a metric emitted by the source sprint's own test-card "
    "engine — nothing here re-computes the physics."
)

with st.sidebar:
    st.subheader("Repository")
    st.code(str(repo_root()))
    if st.button("Reload evidence"):
        st.session_state.pop("rollup", None)
    st.markdown("---")
    st.caption(
        "Honesty note: all sprint 7–9 telemetry is synthetic simulator "
        "output. Nothing here implies real flight or real battery hardware."
    )


@st.cache_data(show_spinner=False)
def _cached_rollup(repo: str, cache_bust: float):
    return build_evidence(Path(repo))


def _get_rollup():
    if "cache_bust" not in st.session_state:
        st.session_state["cache_bust"] = time.time()
    return _cached_rollup(str(repo_root()), st.session_state["cache_bust"])


res = _get_rollup()
summary = run_summary(res)

tabs = st.tabs([
    "Overview", "Traceability matrix", "Requirement drill-in",
    "Inject fault", "Provenance & export",
])

# ------------------------------------------------------------------ 1. Overview
with tabs[0]:
    st.subheader("Fleet-level status")
    fs = summary["fleet_status"]
    st.markdown(f"**Fleet status:** {_badge(fs, STATUS_COLOR.get(fs, '#94a3b8'))}",
                unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Requirements", summary["requirements_total"])
    c2.metric("Passing", summary["requirements_passed"])
    c3.metric("Blocking findings", summary["blocking_findings"])

    st.markdown("### Subsystems")
    for s, status in summary["by_subsystem"].items():
        st.markdown(
            f"- **{s}**: {_badge(status, STATUS_COLOR.get(status, '#94a3b8'))}",
            unsafe_allow_html=True,
        )

    st.markdown("### Catalog")
    st.text(f"Requirements catalog version: {summary['catalog_version']}")
    st.caption(
        "Failing a CRITICAL requirement blocks the subsystem. MAJOR failures "
        "produce a finding that requires a waiver + mitigation. MINOR is "
        "informational."
    )

# ------------------------------------------------------------------ 2. Matrix
with tabs[1]:
    st.subheader("Traceability matrix")
    df = _requirement_df(res)
    df["Status"] = df["Status"].map(lambda s: PASS_ICON[s == "PASS"] + " " + s)
    st.dataframe(
        df,
        hide_index=True, width="stretch",
        column_config={
            "Value": st.column_config.NumberColumn(format="%.4g"),
            "Bound": st.column_config.NumberColumn(format="%.4g"),
        },
    )
    st.caption(
        "One row = one verifiable requirement, aggregated across every "
        "relevant run in the source-sprint artefact. Artefact hash is the "
        "SHA-256 (first 12 chars) of the JSON file the numbers came from."
    )

# ------------------------------------------------------------------ 3. Drill-in
with tabs[2]:
    st.subheader("Requirement drill-in")
    ids = [r.requirement.id for r in res.all_results()]
    pick = st.selectbox("Requirement", ids)
    r = next((x for x in res.all_results() if x.requirement.id == pick), None)
    if r is None:
        st.info("No requirement selected.")
    else:
        req = r.requirement
        st.markdown(f"**{req.id} — {req.title}**")
        st.caption(f"Subsystem: `{req.subsystem.value}`  "
                   f"·  Severity: `{req.severity.value}`  "
                   f"·  Artefact role: `{req.artefact_role}`")
        st.markdown(f"*Rationale.* {req.rationale}")

        cA, cB, cC = st.columns(3)
        cA.metric("Bound", f"{req.op} {req.bound} {req.unit}")
        cB.metric("Aggregated value", f"{r.aggregated_value}")
        cC.metric("Status", r.status)

        if r.note:
            st.info(r.note)

        st.markdown("**Per-run evidence**")
        ev_rows = []
        for e in r.evidence:
            ev_rows.append({
                "Scenario": e.scenario,
                "Seed": e.seed,
                "Value": e.value,
                "Row pass": PASS_ICON[e.passed] + (" PASS" if e.passed else " FAIL"),
                "Triage": e.triage_label or "—",
            })
        if ev_rows:
            st.dataframe(pd.DataFrame(ev_rows),
                         hide_index=True, width="stretch")
        else:
            st.write("_No per-run evidence for this requirement (aggregate-only)._")

        st.markdown("**Provenance**")
        st.code(f"artefact: {r.artefact_path}\nsha256:   {r.artefact_hash}")

# ------------------------------------------------------------------ 4. Inject
with tabs[3]:
    st.subheader("Inject a fault — re-run the source campaign")
    st.caption(
        "This subshells the source sprint's own campaign runner "
        "(same script the sprint's README shows), waits for it to write "
        "fresh artefacts into its own data/ folder, then re-reads them. "
        "The traceability matrix updates in place."
    )
    plans = available_injections(repo_root())
    plan_labels = [f"{p.subsystem.value} — {p.label}" for p in plans]
    idx = st.selectbox("Injection", range(len(plans)),
                       format_func=lambda i: plan_labels[i])
    plan = plans[idx]
    st.code(f"cwd: {plan.cwd}\ncmd: {' '.join(plan.command)}\n"
            f"timeout: {plan.timeout_s}s")

    if st.button("Run injection", type="primary"):
        log_box = st.empty()
        buffer = io.StringIO()

        def _progress(msg: str):
            buffer.write(msg)
            log_box.code(buffer.getvalue())

        with st.spinner(f"Running {plan.label} …"):
            result = run_injection(plan, repo_root(), progress=_progress)
        if result.exit_code == 0:
            st.success(f"Injection completed (exit {result.exit_code}).")
        else:
            st.error(f"Injection returned exit {result.exit_code}.")
        with st.expander("Injection stdout"):
            st.code(result.stdout or "(empty)")
        if result.stderr:
            with st.expander("Injection stderr"):
                st.code(result.stderr)

        # Bust the cache so the other tabs see fresh evidence next render.
        st.session_state["cache_bust"] = time.time()
        st.info("Evidence reloaded — switch back to the Traceability tab.")

# ------------------------------------------------------------------ 5. Provenance
with tabs[4]:
    st.subheader("Artefact manifest")
    man_rows = []
    for rec in res.manifest:
        man_rows.append({
            "Subsystem": rec.subsystem,
            "Role": rec.role,
            "Path": str(rec.path),
            "SHA-256 (12)": rec.sha256_12,
            "Bytes": rec.bytes_,
            "Present": PASS_ICON[rec.exists],
        })
    st.dataframe(pd.DataFrame(man_rows), hide_index=True,
                 width="stretch")

    st.markdown("### Export evidence package")
    st.caption(
        "One-page PDF: fleet status, per-subsystem status, every "
        "requirement row, and the manifest hash footer — the artefact "
        "you would hand to a DER / reviewer."
    )
    if st.button("Generate PDF"):
        from scripts import export_evidence  # local import
        out_pdf = repo_root() / "sprint10_fleet_certification" / "reports" / \
                  f"fleet_evidence_{int(time.time())}.pdf"
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        export_evidence.write_pdf(res, out_pdf)
        st.success(f"Wrote {out_pdf}")
        with out_pdf.open("rb") as f:
            st.download_button(
                "Download PDF", f, file_name=out_pdf.name,
                mime="application/pdf",
            )
