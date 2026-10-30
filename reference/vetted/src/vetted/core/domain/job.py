"""Listing-side domain models.

Every field that a capture may omit is typed `X | Unknown`, so absence survives normalization
and can never be silently replaced by a guess.

`years_of_experience_requirement` is a fact stated by the *listing*. It is not a candidate
figure, and nothing derives a candidate years-of-experience value from it (D-4).
"""

from vetted.core.domain import UNKNOWN, FrozenModel, Unknown
from vetted.core.enums import EmploymentType, RelocationStatus, WorkArrangementType

__all__ = [
    "CompanyFacts",
    "CompensationFacts",
    "JobProvenance",
    "NormalizedJob",
    "WorkArrangementFacts",
]


class JobProvenance(FrozenModel):
    """Immutable capture provenance. Written once, never rewritten."""

    source_platform: str
    source_url: str | Unknown = UNKNOWN
    import_method: str = "manual_copy_paste"
    captured_at: str = UNKNOWN
    stated_posting_date: str | Unknown = UNKNOWN


class CompanyFacts(FrozenModel):
    """Employer facts as captured.

    Absence of a website or careers URL is missing evidence, never negative evidence, and
    never a hard blocker (D-6).
    """

    company_name: str
    company_website: str | Unknown = UNKNOWN
    official_careers_url: str | Unknown = UNKNOWN
    company_stage_or_size: str | Unknown = UNKNOWN


class WorkArrangementFacts(FrozenModel):
    """Location, arrangement, relocation, authorization, and clearance facts as captured."""

    employment_type: EmploymentType = EmploymentType.UNKNOWN
    work_arrangement: WorkArrangementType = WorkArrangementType.UNKNOWN
    relocation_status: RelocationStatus = RelocationStatus.UNKNOWN
    location_text: str | Unknown = UNKNOWN
    state_restrictions: str | Unknown = UNKNOWN
    time_zone_restrictions: str | Unknown = UNKNOWN
    work_authorization_requirements: str | Unknown = UNKNOWN
    clearance_requirements: str | Unknown = UNKNOWN


class CompensationFacts(FrozenModel):
    """Compensation facts as captured.

    Hourly and contract figures are kept separate from base salary and are never annualized
    or equated to salary (D-3).
    """

    base_salary_min_usd: int | Unknown = UNKNOWN
    base_salary_max_usd: int | Unknown = UNKNOWN
    hourly_rate_min_usd: int | Unknown = UNKNOWN
    hourly_rate_max_usd: int | Unknown = UNKNOWN
    contract_term: str | Unknown = UNKNOWN


class NormalizedJob(FrozenModel):
    """A normalized listing. Absent values remain UNKNOWN."""

    job_id: str
    job_title: str
    provenance: JobProvenance
    company: CompanyFacts
    work: WorkArrangementFacts
    compensation: CompensationFacts
    responsibilities: str | Unknown = UNKNOWN
    required_qualifications: str | Unknown = UNKNOWN
    preferred_qualifications: str | Unknown = UNKNOWN
    education_requirements: str | Unknown = UNKNOWN
    years_of_experience_requirement: str | Unknown = UNKNOWN
    required_technologies: tuple[str, ...] = ()
