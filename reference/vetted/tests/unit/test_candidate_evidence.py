"""Candidate evidence loader tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from vetted.candidate.evidence import load_evidence_records
from vetted.exceptions import EvidenceValidationError


def test_evidence_loader_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(EvidenceValidationError, match="Evidence directory"):
        load_evidence_records(tmp_path / "missing")


def test_evidence_loader_rejects_empty_directory(tmp_path: Path) -> None:
    evidence_directory = tmp_path / "evidence"
    evidence_directory.mkdir()

    with pytest.raises(EvidenceValidationError, match="No YAML evidence records"):
        load_evidence_records(evidence_directory)
