"""Generate a one-page certification evidence PDF from a rollup.

The PDF is intentionally boring — the point is that it looks like
something a DER / reviewer already knows how to read:

  1. Header: catalog version, date, fleet status
  2. Subsystem status band
  3. Requirement table: ID, requirement, bound, value, status, severity
  4. Manifest footer: every artefact hash referenced above

Reportlab is used because it is dependency-light and produces
deterministic output; no headless-browser rendering.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

# Support both `python -m scripts.export_evidence` and direct execution.
if __package__ in (None, ""):
    HERE = Path(__file__).resolve().parent
    sys.path.insert(0, str(HERE.parent))

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from polaris_fc import build_evidence, run_summary
from polaris_fc.evidence import RollupResult


STATUS_FILL = {
    "GREEN": colors.HexColor("#dcfce7"),
    "FINDINGS": colors.HexColor("#fef3c7"),
    "BLOCKED": colors.HexColor("#fee2e2"),
    "NO_EVIDENCE": colors.HexColor("#e2e8f0"),
    "PASS": colors.HexColor("#dcfce7"),
    "FAIL": colors.HexColor("#fee2e2"),
}


def _fmt(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        if v != v:  # NaN
            return "NaN"
        return f"{v:.4g}"
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v)


def write_pdf(res: RollupResult, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary = run_summary(res)

    doc = SimpleDocTemplate(
        str(out_path), pagesize=LETTER,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
    )
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]; h1.fontSize = 16
    h2 = styles["Heading2"]; h2.fontSize = 11
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=8,
                           leading=10, textColor=colors.grey)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9,
                          leading=11)

    story = []
    story.append(Paragraph("Polaris — Fleet Certification Evidence Package", h1))
    story.append(Paragraph(
        f"Catalog v{summary['catalog_version']} · "
        f"Generated {dt.datetime.utcnow().isoformat(timespec='seconds')}Z · "
        f"Fleet status: <b>{summary['fleet_status']}</b>",
        body))
    story.append(Spacer(1, 0.15 * inch))

    # Subsystem status band
    band_rows = [["Subsystem", "Status"]]
    for s, status in summary["by_subsystem"].items():
        band_rows.append([s, status])
    band = Table(band_rows, colWidths=[2.6 * inch, 1.4 * inch])
    band_style = TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.grey),
    ])
    for i, (_, status) in enumerate(list(summary["by_subsystem"].items()), start=1):
        band_style.add("BACKGROUND", (1, i), (1, i),
                       STATUS_FILL.get(status, colors.white))
    band.setStyle(band_style)
    story.append(band)
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Requirements traceability", h2))
    hdr = ["ID", "Requirement", "Bound", "Value", "N", "Status", "Sev", "Hash"]
    rows = [hdr]
    for r in res.all_results():
        req = r.requirement
        rows.append([
            req.id,
            Paragraph(req.title, body),
            f"{req.op} {req.bound}",
            _fmt(r.aggregated_value),
            r.n_runs_considered,
            r.status,
            req.severity.value,
            r.artefact_hash,
        ])
    tbl = Table(rows, repeatRows=1, colWidths=[
        0.9 * inch, 2.5 * inch, 0.7 * inch, 0.6 * inch, 0.35 * inch,
        0.55 * inch, 0.55 * inch, 0.85 * inch,
    ])
    tstyle = TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.lightgrey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ])
    for i, r in enumerate(res.all_results(), start=1):
        tstyle.add("BACKGROUND", (5, i), (5, i),
                   STATUS_FILL.get(r.status, colors.white))
    tbl.setStyle(tstyle)
    story.append(tbl)
    story.append(Spacer(1, 0.18 * inch))

    # Manifest footer
    story.append(Paragraph("Artefact manifest (SHA-256, first 12 chars)", h2))
    m_rows = [["Subsystem", "Role", "Path", "Hash", "Present"]]
    for rec in res.manifest:
        m_rows.append([
            rec.subsystem, rec.role, str(rec.path.name),
            rec.sha256_12, "yes" if rec.exists else "no",
        ])
    m = Table(m_rows, repeatRows=1, colWidths=[
        1.4 * inch, 1.2 * inch, 1.8 * inch, 0.9 * inch, 0.6 * inch,
    ])
    m.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.lightgrey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
    ]))
    story.append(m)
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        "All source telemetry is synthetic simulator output. This package "
        "records what the sprint 7–9 test-card engines emitted for the "
        "artefact bytes hashed above; it does not claim provenance for any "
        "physical hardware.", small))

    doc.build(story)
    return out_path


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[2]),
                    help="Repository root containing sprint7/8/9 folders.")
    ap.add_argument("--out", default=None, help="PDF output path.")
    args = ap.parse_args()

    repo = Path(args.repo)
    res = build_evidence(repo)
    out = Path(args.out) if args.out else (
        Path(__file__).resolve().parents[1] / "reports" /
        f"fleet_evidence_{dt.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.pdf"
    )
    write_pdf(res, out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
