"""Parse an approved job capture into a `NormalizedJob`.

Parsing is by labelled field. No line number is ever used (standing ruling A-1), and no field
position is assumed: a capture may omit any optional field, reorder fields, or omit whole
sections. Every absent value becomes `UNKNOWN`.

Nothing is guessed. An unparseable enum value or a non-integer salary raises `CaptureFormatError`
naming the field and what was accepted, rather than falling back to `UNKNOWN` — a fallback would
turn a typo into silent data loss. The template's import rule requires exactly this: "preserve
source text, mark absent values UNKNOWN, and avoid guessing".

Template fields with no destination are discarded, which is deliberate for
`public_recruiter_or_contact` (D-9) and incidental for `company_description`, `remote_details`,
`travel_requirements`, `total_compensation`, `bonus`, `equity`, `benefits`,
`application_instructions`, `owner_notes`, and `raw_listing_text`. A future model change may give
some of them a home; none may acquire one by inference here.
"""

from typing import Any

from vetted.core.domain import UNKNOWN, Unknown
from vetted.core.domain.job import (
    CompanyFacts,
    CompensationFacts,
    JobProvenance,
    NormalizedJob,
    WorkArrangementFacts,
)
from vetted.core.enums import EmploymentType, RelocationStatus, WorkArrangementType

__all__ = [
    "BLOCK_FIELDS",
    "DISCARDED_FIELDS",
    "CaptureFormatError",
    "parse_capture",
    "parse_fields",
]

FRONTMATTER_FENCE = "---"

BLOCK_FIELDS: frozenset[str] = frozenset(
    {
        "responsibilities",
        "required_qualifications",
        "preferred_qualifications",
        "education_requirements",
        "required_technologies",
        "raw_listing_text",
    }
)
"""Fields the template writes as an indented block under `key: |`."""

DISCARDED_FIELDS: frozenset[str] = frozenset(
    {
        "public_recruiter_or_contact",
        "owner_notes",
        "company_description",
        "remote_details",
        "travel_requirements",
        "total_compensation",
        "bonus",
        "equity",
        "benefits",
        "application_instructions",
        "raw_listing_text",
    }
)
"""Captured fields with no destination. `public_recruiter_or_contact` is dropped by D-9."""

_ENUM_FIELDS = {
    "employment_type": EmploymentType,
    "work_arrangement": WorkArrangementType,
    "relocation_status": RelocationStatus,
}

_INT_FIELDS = (
    "base_salary_min_usd",
    "base_salary_max_usd",
    "hourly_rate_min_usd",
    "hourly_rate_max_usd",
)


class CaptureFormatError(ValueError):
    """A captured value could not be read, and guessing one is not permitted."""


def _unquote(value: str) -> str:
    text = value.strip()
    for quote in ('"', "'"):
        if len(text) >= 2 and text.startswith(quote) and text.endswith(quote):
            return text[1:-1]
    return text


def parse_fields(text: str) -> dict[str, str]:
    """Return every labelled field in the capture, by name, with raw string values.

    Handles the YAML frontmatter, `# Section` headings, `key: value` scalars, and `key: |`
    indented blocks. A duplicate field name raises: silently keeping one of two values would
    lose captured source text.
    """
    fields: dict[str, str] = {}
    lines = text.splitlines()
    index = 0
    if lines and lines[0].strip() == FRONTMATTER_FENCE:
        index = 1

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        index += 1
        if not stripped or stripped == FRONTMATTER_FENCE or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise CaptureFormatError(
                f"capture line is neither a heading nor a labelled field: {stripped!r}"
            )
        name, _, remainder = stripped.partition(":")
        name = name.strip()
        remainder = remainder.strip()
        if name in fields:
            raise CaptureFormatError(f"field {name!r} appears more than once in the capture")
        if remainder == "|":
            block: list[str] = []
            while index < len(lines):
                candidate = lines[index]
                if candidate.strip() and not candidate.startswith((" ", "\t")):
                    break
                block.append(candidate.strip())
                index += 1
            fields[name] = "\n".join(block).strip()
        else:
            fields[name] = _unquote(remainder)
    return fields


def _text(fields: dict[str, str], name: str) -> str | Unknown:
    value = fields.get(name, "").strip()
    if not value or value == UNKNOWN:
        return UNKNOWN
    return value


def _required_text(fields: dict[str, str], name: str) -> str:
    value = fields.get(name, "").strip()
    if not value or value == UNKNOWN:
        raise CaptureFormatError(
            f"{name} is required and must not be blank or {UNKNOWN}; a capture without it "
            "cannot be assessed"
        )
    return value


def _integer(fields: dict[str, str], name: str) -> int | Unknown:
    value = fields.get(name, "").strip()
    if not value or value == UNKNOWN:
        return UNKNOWN
    try:
        return int(value)
    except ValueError:
        raise CaptureFormatError(
            f"{name} must be a plain integer of US dollars or {UNKNOWN}, got {value!r}. "
            "Currency symbols, thousands separators, and ranges are not interpreted, because "
            "compensation is never guessed. Enter the figure as digits only."
        ) from None


def _enum(fields: dict[str, str], name: str) -> Any:  # one of the _ENUM_FIELDS types
    enum_type = _ENUM_FIELDS[name]
    value = fields.get(name, "").strip()
    if not value:
        return enum_type["UNKNOWN"]
    try:
        return enum_type(value)
    except ValueError:
        permitted = ", ".join(member.value for member in enum_type)
        raise CaptureFormatError(
            f"{name} must be one of: {permitted}. Got {value!r}. An unrecognized value is not "
            f"treated as {UNKNOWN}, because that would turn a typo into silent data loss."
        ) from None


def _technologies(fields: dict[str, str]) -> tuple[str, ...]:
    """One required technology per line, exactly as approved.

    A line is never split on a comma and never stripped of a bullet: both would be delimiter
    rules the owner has not approved, and A-6 permits only four normalization steps, which
    belong to the matcher. A comma-separated line therefore arrives as one phrase and will not
    match, which is visible rather than silent.
    """
    block = fields.get("required_technologies", "")
    return tuple(line.strip() for line in block.splitlines() if line.strip())


def parse_capture(text: str, job_id: str) -> NormalizedJob:
    """Parse an approved capture into a `NormalizedJob`.

    `job_id` is supplied by the caller rather than derived. The template carries no identifier,
    and inventing one would be a value this module has no authority to create.
    """
    if not job_id.strip():
        raise CaptureFormatError("job_id must be supplied by the caller and must not be blank")
    fields = parse_fields(text)
    return NormalizedJob(
        job_id=job_id.strip(),
        job_title=_required_text(fields, "job_title"),
        provenance=JobProvenance(
            source_platform=_required_text(fields, "source_platform"),
            source_url=_text(fields, "source_url"),
            import_method=fields.get("import_method", "").strip() or "manual_copy_paste",
            captured_at=_text(fields, "captured_at"),
            stated_posting_date=_text(fields, "stated_posting_date"),
        ),
        company=CompanyFacts(
            company_name=_required_text(fields, "company_name"),
            company_website=_text(fields, "company_website"),
            official_careers_url=_text(fields, "official_careers_url"),
            company_stage_or_size=_text(fields, "company_stage_or_size"),
        ),
        work=WorkArrangementFacts(
            employment_type=_enum(fields, "employment_type"),
            work_arrangement=_enum(fields, "work_arrangement"),
            relocation_status=_enum(fields, "relocation_status"),
            location_text=_text(fields, "location_text"),
            state_restrictions=_text(fields, "state_restrictions"),
            time_zone_restrictions=_text(fields, "time_zone_restrictions"),
            work_authorization_requirements=_text(
                fields, "work_authorization_requirements"
            ),
            clearance_requirements=_text(fields, "clearance_requirements"),
        ),
        compensation=CompensationFacts(
            **{name: _integer(fields, name) for name in _INT_FIELDS},
            contract_term=_text(fields, "contract_term"),
        ),
        responsibilities=_text(fields, "responsibilities"),
        required_qualifications=_text(fields, "required_qualifications"),
        preferred_qualifications=_text(fields, "preferred_qualifications"),
        education_requirements=_text(fields, "education_requirements"),
        years_of_experience_requirement=_text(fields, "years_of_experience"),
        required_technologies=_technologies(fields),
    )
