"""Pydantic schemas for candidate data and source-traceable evidence."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)

EvidenceId = Annotated[
    str,
    StringConstraints(
        pattern=r"^EV-[A-Z0-9][A-Z0-9_-]{2,80}$",
        min_length=5,
        max_length=84,
    ),
]

EvidenceTag = Annotated[
    str,
    StringConstraints(
        pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$",
        min_length=2,
        max_length=64,
    ),
]


class CandidateProfile(BaseModel):
    """Verified public candidate identity and professional link information."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["1"] = "1"
    full_name: Annotated[str, StringConstraints(min_length=2, max_length=120)]
    location: Annotated[str, StringConstraints(min_length=2, max_length=160)]
    email: EmailStr
    phone: Annotated[
        str,
        StringConstraints(
            pattern=r"^\+?[0-9][0-9(). -]{6,30}$",
            min_length=7,
            max_length=32,
        ),
    ]
    linkedin_url: AnyHttpUrl
    portfolio_url: AnyHttpUrl
    github_url: AnyHttpUrl
    approved_for_safe_autofill: bool = False
    source_classification: Literal["resume"] = "resume"
    confidence: Literal["verified"] = "verified"

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin_host(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """Require a LinkedIn URL in the designated field."""
        if value.host not in {"linkedin.com", "www.linkedin.com"}:
            raise ValueError("linkedin_url must use linkedin.com.")
        return value

    @field_validator("github_url")
    @classmethod
    def validate_github_host(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """Require a GitHub URL in the designated field."""
        if value.host not in {"github.com", "www.github.com"}:
            raise ValueError("github_url must use github.com.")
        return value


class EvidenceRecord(BaseModel):
    """One atomic verified claim derived from an approved source document."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    evidence_id: EvidenceId
    category: Literal[
        "identity_and_links",
        "professional_positioning",
        "applied_ai_rag",
        "software_automation",
        "qa_reliability",
        "systems_networking",
        "delivery_communication",
        "metrics",
        "work_experience",
        "education_training",
        "guardrails",
    ]
    factual_statement: Annotated[
        str,
        StringConstraints(min_length=10, max_length=2_000),
    ]
    source_classification: Literal["resume"] = "resume"
    approved_for_external_use: bool
    confidence: Literal["verified"] = "verified"
    tags: list[EvidenceTag] = Field(min_length=1, max_length=20)
    source_document: Annotated[
        str,
        StringConstraints(min_length=3, max_length=260),
    ] = "00_ag_applied-ai-engineer_resume.pdf"
    source_pages: list[int] = Field(min_length=1, max_length=10)
    source_excerpt: Annotated[
        str,
        StringConstraints(min_length=10, max_length=3_000),
    ]
    recorded_on: date | None = None

    @field_validator("source_pages")
    @classmethod
    def validate_source_pages(cls, value: list[int]) -> list[int]:
        """Require sorted, unique, one-based source-page values."""
        if any(page < 1 for page in value):
            raise ValueError("source_pages must contain only positive page numbers.")
        if value != sorted(set(value)):
            raise ValueError("source_pages must be sorted and unique.")
        return value


class PrivateUserInputs(BaseModel):
    """Sensitive unindexed responses; absent values remain unknown."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    work_authorization: str | None = None
    requires_sponsorship: str | None = None
    compensation_expectations: str | None = None
    availability: str | None = None
    schedule_preferences: str | None = None
    relocation_preference: str | None = None
    travel_preference: str | None = None
    disability_disclosure: str | None = None
    veteran_status: str | None = None
    criminal_history_response: str | None = None
    background_check_response: str | None = None
