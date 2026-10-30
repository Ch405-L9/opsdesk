"""Load and validate local candidate data without network access."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from vetted.exceptions import EvidenceValidationError
from vetted.schemas.candidate import (
    CandidateProfile,
    EvidenceRecord,
)


def load_yaml_mapping(path: Path) -> dict[str, object]:
    """Load one YAML mapping from a UTF-8 local file."""
    if not path.is_file():
        raise EvidenceValidationError(f"Required file does not exist: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise EvidenceValidationError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise EvidenceValidationError(f"Expected a YAML mapping in {path}")

    return raw


def load_candidate_profile(path: Path) -> CandidateProfile:
    """Load and validate the ignored local candidate profile."""
    try:
        return CandidateProfile.model_validate(load_yaml_mapping(path))
    except ValidationError as exc:
        raise EvidenceValidationError(
            f"Candidate profile validation failed for {path}: {exc}"
        ) from exc


def load_evidence_records(evidence_path: Path) -> list[EvidenceRecord]:
    """Load reviewed atomic evidence records in deterministic filename order."""
    if not evidence_path.is_dir():
        raise EvidenceValidationError(
            f"Evidence directory does not exist: {evidence_path}"
        )

    records: list[EvidenceRecord] = []
    known_ids: set[str] = set()

    for path in sorted(evidence_path.glob("*.yaml")):
        try:
            record = EvidenceRecord.model_validate(load_yaml_mapping(path))
        except ValidationError as exc:
            raise EvidenceValidationError(
                f"Evidence validation failed for {path}: {exc}"
            ) from exc

        if record.evidence_id in known_ids:
            raise EvidenceValidationError(
                f"Duplicate evidence_id found: {record.evidence_id}"
            )

        known_ids.add(record.evidence_id)
        records.append(record)

    if not records:
        raise EvidenceValidationError(
            f"No YAML evidence records were found in {evidence_path}"
        )

    return records


def validate_candidate_data(
    candidate_root: Path,
) -> tuple[CandidateProfile, list[EvidenceRecord]]:
    """Validate local candidate profile and all reviewed evidence."""
    profile = load_candidate_profile(candidate_root / "candidate_profile.yaml")
    records = load_evidence_records(candidate_root / "evidence")
    return profile, records
