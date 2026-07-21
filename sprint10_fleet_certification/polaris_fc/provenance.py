"""Evidence provenance: hash + manifest so a claim can be traced to bytes.

An evidence package is only useful if the reader can verify that the
numbers on the page were computed from the exact artefact bytes they can
still inspect. Each artefact is hashed (SHA-256, truncated to 12 hex chars
for readability) and the console pins that hash next to every claim.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class ArtefactRecord:
    subsystem: str            # BATTERY_PACK | FIXED_WING_UAV | LANDING_MULTIROTOR
    role: str                 # e.g. "campaign", "triage", "estimator_benchmark"
    path: Path
    sha256_12: str
    bytes_: int
    exists: bool


def evidence_hash(path: Path) -> str:
    """SHA-256 of the artefact bytes, truncated to 12 hex characters.

    12 hex chars = 48 bits: collision probability among a portfolio of
    O(10^3) artefacts is ~10^-9, plenty for provenance labelling while
    staying readable in a PDF footer.
    """
    if not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def artefact_manifest(repo_root: Path) -> List[ArtefactRecord]:
    """Enumerate the sprint 7-9 artefacts the console depends on.

    Absent files are reported as `exists=False` rather than raising, so a
    partial deployment (e.g. only sprint 8 present) still renders a
    partial matrix instead of erroring the whole console.
    """
    plan = [
        ("BATTERY_PACK", "estimator_benchmark",
         "sprint7_battery_testbench/data/estimator_benchmark.json"),
        ("BATTERY_PACK", "triage_model",
         "sprint7_battery_testbench/data/triage_model.json"),
        ("BATTERY_PACK", "rul_projections",
         "sprint7_battery_testbench/data/rul_projections.json"),
        ("BATTERY_PACK", "cycle_records",
         "sprint7_battery_testbench/data/cycle_records.json"),
        ("FIXED_WING_UAV", "campaign",
         "sprint8_flight_test_harness/data/campaign.json"),
        ("FIXED_WING_UAV", "triage",
         "sprint8_flight_test_harness/data/triage.json"),
        ("LANDING_MULTIROTOR", "campaign",
         "sprint9_precision_landing/data/campaign.json"),
        ("LANDING_MULTIROTOR", "triage",
         "sprint9_precision_landing/data/triage.json"),
    ]
    out: List[ArtefactRecord] = []
    for subsystem, role, rel in plan:
        p = repo_root / rel
        if p.exists():
            out.append(ArtefactRecord(
                subsystem=subsystem, role=role, path=p,
                sha256_12=evidence_hash(p), bytes_=p.stat().st_size, exists=True))
        else:
            out.append(ArtefactRecord(
                subsystem=subsystem, role=role, path=p,
                sha256_12="MISSING", bytes_=0, exists=False))
    return out


def manifest_as_dict(records: List[ArtefactRecord]) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for r in records:
        out.setdefault(r.subsystem, {})[r.role] = r.sha256_12
    return out


def load_json(path: Path):
    """Load a JSON artefact, returning None if missing."""
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)
