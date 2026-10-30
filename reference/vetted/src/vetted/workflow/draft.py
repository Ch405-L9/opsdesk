"""Build review-only local draft metadata from validated candidate evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vetted.candidate.evidence import load_evidence_records
from vetted.safety import NO_SUBMIT_STATEMENT, enforce_no_submit
from vetted.settings import Settings


@dataclass(frozen=True)
class DraftArtifact:
    """In-memory review artifact; no external or persistent action is performed."""

    evidence_record_count: int
    status: str
    submission_statement: str


def build_local_draft(settings: Settings) -> DraftArtifact:
    """Validate local evidence and return an in-memory review-only draft summary."""
    enforce_no_submit(settings)

    evidence_root: Path = settings.candidate_data_path / "evidence"
    records = load_evidence_records(evidence_root)

    return DraftArtifact(
        evidence_record_count=len(records),
        status="review_required",
        submission_statement=NO_SUBMIT_STATEMENT,
    )
