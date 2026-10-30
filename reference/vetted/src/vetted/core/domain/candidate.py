"""Candidate-side domain models.

Deliberately absent, and asserted absent by tests/compliance/test_no_contact_fields.py:

* contact fields of any kind - email, phone, address (D-9);
* business ownership, legal officer, equity, or LLC membership fields (D-2);
* any total-years-of-experience field, and any date-arithmetic helper (D-4).

Employment dates are opaque strings, never date objects, so no code can subtract them to
manufacture a years-of-experience figure.
"""

from vetted.core.domain import UNKNOWN, FrozenModel, Unknown
from vetted.core.enums import EvidenceTier

__all__ = [
    "CandidateDossier",
    "EmploymentEvidence",
    "ProjectEvidence",
    "SkillEvidence",
    "TrainingEvidence",
    "WorkPreferences",
]


class SkillEvidence(FrozenModel):
    """A skill together with the tier of evidence that supports it (D-7)."""

    name: str
    tier: EvidenceTier


class ProjectEvidence(FrozenModel):
    """A verified project. Supports EvidenceTier.TIER_2_PROJECT_EVIDENCE matches."""

    name: str
    technologies: tuple[str, ...]
    summary: str
    qualifier: str | Unknown = UNKNOWN


class EmploymentEvidence(FrozenModel):
    """A verified employment record. Supports TIER_3_EMPLOYMENT_EVIDENCE matches.

    `start` and `end` are opaque display strings such as "January 2025" and "Present".
    They are never parsed into dates and never used in arithmetic (D-4).
    """

    title: str
    organization: str
    location: str
    start: str
    end: str
    technologies: tuple[str, ...]
    responsibilities: tuple[str, ...]


class TrainingEvidence(FrozenModel):
    """Training or coursework. Supports TIER_4_TRAINING matches only."""

    name: str
    provider: str


class WorkPreferences(FrozenModel):
    """Approved work preferences.

    `work_authorization` is typed as the UNKNOWN sentinel and nothing else, so no
    authorization value can be stored in tracked project data (D-5).
    """

    target_country: str
    remote_preference: str
    relocation_willing: bool
    relocation_assistance_preferred: bool
    preferred_base_salary_min_usd: int
    exclusion_floor_base_salary_usd: int
    work_authorization: Unknown = UNKNOWN


class CandidateDossier(FrozenModel):
    """The sole candidate-qualification source of truth.

    Never fabricate, infer, or extend these facts. A job listing can never modify a dossier.
    """

    name: str
    base_location: str
    preferences: WorkPreferences
    positioning_statement: str
    target_role_families: tuple[str, ...]
    avoid_role_families: tuple[str, ...]
    verified_skills: tuple[SkillEvidence, ...]
    project_evidence: tuple[ProjectEvidence, ...]
    employment_evidence: tuple[EmploymentEvidence, ...]
    training_evidence: tuple[TrainingEvidence, ...]
    prohibited_inferences: tuple[str, ...]
