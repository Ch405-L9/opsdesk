"""Candidate profile and atomic evidence schema tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vetted.schemas.candidate import CandidateProfile, EvidenceRecord


def test_candidate_profile_accepts_verified_public_data() -> None:
    profile = CandidateProfile(
        full_name="Example Candidate",
        location="Example City, Georgia",
        email="candidate@example.com",
        phone="470-555-1234",
        linkedin_url="https://linkedin.com/in/example-candidate",
        portfolio_url="https://example.com/portfolio",
        github_url="https://github.com/example-candidate",
        approved_for_safe_autofill=False,
        source_classification="resume",
        confidence="verified",
    )

    assert profile.full_name == "Example Candidate"
    assert profile.approved_for_safe_autofill is False


def test_candidate_profile_rejects_non_linkedin_url() -> None:
    with pytest.raises(ValidationError, match="linkedin_url must use linkedin.com"):
        CandidateProfile(
            full_name="Example Candidate",
            location="Example City, Georgia",
            email="candidate@example.com",
            phone="470-555-1234",
            linkedin_url="https://example.com/not-linkedin",
            portfolio_url="https://example.com/portfolio",
            github_url="https://github.com/example-candidate",
            source_classification="resume",
            confidence="verified",
        )


def test_evidence_record_requires_sorted_unique_source_pages() -> None:
    with pytest.raises(ValidationError, match="sorted and unique"):
        EvidenceRecord(
            evidence_id="EV-TEST-001",
            category="applied_ai_rag",
            factual_statement="A sufficiently long verified factual statement for schema testing.",
            source_classification="resume",
            approved_for_external_use=True,
            confidence="verified",
            tags=["testing", "evidence"],
            source_pages=[2, 1, 1],
            source_excerpt="A sufficiently long source excerpt for schema testing.",
        )


def test_evidence_record_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EvidenceRecord(
            evidence_id="EV-TEST-002",
            category="applied_ai_rag",
            factual_statement="A sufficiently long verified factual statement for schema testing.",
            source_classification="resume",
            approved_for_external_use=True,
            confidence="verified",
            tags=["testing", "evidence"],
            source_pages=[1],
            source_excerpt="A sufficiently long source excerpt for schema testing.",
            unsupported_field="not permitted",
        )
