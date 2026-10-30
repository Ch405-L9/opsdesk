"""Capture import.

Capture text is built inline here rather than added as a fixture file: the compliance test
`test_no_real_captures_committed` permits exactly the two existing synthetic captures, and
adding a third would weaken it. Every capture below is invented.

Parsing is by labelled field. These tests assert that no field position is relied on, that
absence becomes UNKNOWN, and that a malformed value raises rather than degrading quietly.
"""

import ast
from pathlib import Path

import pytest

from vetted.core.domain import UNKNOWN
from vetted.core.enums import EmploymentType, RelocationStatus, WorkArrangementType
from vetted.core.ingest.capture import (
    DISCARDED_FIELDS,
    CaptureFormatError,
    parse_capture,
    parse_fields,
)

FULL = """---
source_platform: wellfound
source_url: "UNKNOWN"
import_method: manual_copy_paste
captured_at: "UNKNOWN"
stated_posting_date: "UNKNOWN"
owner_notes: "Invented capture used only for tests."
---

# Job identity

job_title: "Applied AI Engineer"
company_name: "Invented Analytics"
company_website: "UNKNOWN"
official_careers_url: "UNKNOWN"
company_description: "An invented company."
company_stage_or_size: "UNKNOWN"

# Work arrangement

employment_type: "FULL_TIME"
location_text: "Remote, United States"
work_arrangement: "US_REMOTE"
relocation_status: "NOT_MENTIONED"
state_restrictions: "UNKNOWN"
time_zone_restrictions: "UNKNOWN"
work_authorization_requirements: "UNKNOWN"
clearance_requirements: "UNKNOWN"

# Compensation

base_salary_min_usd: 110000
base_salary_max_usd: 130000
hourly_rate_min_usd: "UNKNOWN"
hourly_rate_max_usd: "UNKNOWN"
contract_term: "UNKNOWN"

# Role content

responsibilities: |
  Build invented things.
required_qualifications: |
  Invented requirement.
preferred_qualifications: |
  Invented preference.
education_requirements: "Bachelor's degree or equivalent experience."
years_of_experience: "2+ years"
required_technologies: |
  Python
  RAG
  React.js

# Hiring and application

public_recruiter_or_contact: "someone@invented.example"
application_instructions: "UNKNOWN"

# Raw listing text

raw_listing_text: |
  Invented listing body.
"""

MINIMAL = """---
source_platform: wellfound
---

job_title: "Invented Role"
company_name: "Invented Co"
"""


def _job(text: str = FULL, job_id: str = "synthetic-1"):
    return parse_capture(text, job_id)


# ------------------------------------------------------------------- happy path


def test_every_mapped_field_arrives() -> None:
    job = _job()
    assert job.job_id == "synthetic-1"
    assert job.job_title == "Applied AI Engineer"
    assert job.company.company_name == "Invented Analytics"
    assert job.provenance.source_platform == "wellfound"
    assert job.work.employment_type is EmploymentType.FULL_TIME
    assert job.work.work_arrangement is WorkArrangementType.US_REMOTE
    assert job.work.relocation_status is RelocationStatus.NOT_MENTIONED
    assert job.work.location_text == "Remote, United States"
    assert job.compensation.base_salary_min_usd == 110_000
    assert job.compensation.base_salary_max_usd == 130_000
    assert job.years_of_experience_requirement == "2+ years"
    assert job.responsibilities == "Build invented things."


def test_quotes_are_stripped_but_inner_text_is_preserved() -> None:
    assert _job().education_requirements == "Bachelor's degree or equivalent experience."


def test_parsing_is_deterministic() -> None:
    assert _job() == _job()


def test_both_shipped_synthetic_captures_parse(repo_root: Path) -> None:
    captures = repo_root / "tests" / "core" / "fixtures" / "captures"
    for path in sorted(captures.glob("*.md")):
        job = parse_capture(path.read_text(encoding="utf-8"), path.stem)
        assert job.job_title
        assert job.company.company_name


# ------------------------------------------------------------- absence is UNKNOWN


def test_absent_fields_become_unknown() -> None:
    """The template's own rule: mark absent values UNKNOWN and avoid guessing."""
    job = _job(MINIMAL)
    assert job.work.employment_type is EmploymentType.UNKNOWN
    assert job.work.work_arrangement is WorkArrangementType.UNKNOWN
    assert job.work.relocation_status is RelocationStatus.UNKNOWN
    assert job.compensation.base_salary_min_usd == UNKNOWN
    assert job.company.company_website == UNKNOWN
    assert job.responsibilities == UNKNOWN
    assert job.required_technologies == ()


def test_a_literal_unknown_and_an_absent_field_agree() -> None:
    assert _job(MINIMAL).work.clearance_requirements == UNKNOWN
    assert _job().work.clearance_requirements == UNKNOWN


def test_whole_sections_may_be_omitted() -> None:
    assert _job(MINIMAL).job_title == "Invented Role"


# -------------------------------------------------------- no positional assumptions


def test_field_order_does_not_matter() -> None:
    """A-1: no line number and no field position is relied on.

    Scalar fields are reordered and sections are moved. Block fields keep their own indented
    lines, because an indented continuation belongs to the `key: |` above it by construction.
    """
    forward = """---
source_platform: wellfound
---

# Job identity

job_title: "Invented Role"
company_name: "Invented Co"

# Work arrangement

employment_type: "CONTRACT"
work_arrangement: "HYBRID"
"""
    backward = """---
source_platform: wellfound
---

# Work arrangement

work_arrangement: "HYBRID"
employment_type: "CONTRACT"

# Job identity

company_name: "Invented Co"
job_title: "Invented Role"
"""
    assert parse_capture(forward, "x") == parse_capture(backward, "x")


def test_a_block_field_survives_a_section_move() -> None:
    """A block and its indented lines move together, so relocating a section is safe."""
    first = FULL
    lines = FULL.splitlines()
    start = lines.index("# Compensation")
    end = lines.index("# Role content")
    moved = lines[:start] + lines[end:] + lines[start:end]
    second = "\n".join(moved) + "\n"
    assert parse_capture(first, "x") == parse_capture(second, "x")


def test_headings_and_blank_lines_are_ignored() -> None:
    fields = parse_fields(FULL)
    assert "Job identity" not in fields
    assert "" not in fields


# --------------------------------------------------- malformed values raise, never guess


@pytest.mark.parametrize(
    "value", ['"$110,000"', '"110,000"', '"110k"', '"110000-130000"', '"about 110000"']
)
def test_a_non_integer_salary_raises(value: str) -> None:
    """Compensation is never guessed, so no currency symbol or separator is interpreted."""
    text = FULL.replace("base_salary_min_usd: 110000", f"base_salary_min_usd: {value}")
    with pytest.raises(CaptureFormatError, match="plain integer"):
        _job(text)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("employment_type", "Full Time"),
        ("employment_type", "full_time"),
        ("work_arrangement", "REMOTE"),
        ("relocation_status", "NONE"),
    ],
)
def test_an_unrecognized_enum_value_raises(field: str, bad: str) -> None:
    """A typo must not silently become UNKNOWN: that is data loss disguised as absence."""
    text = "\n".join(
        f'{field}: "{bad}"' if line.startswith(f"{field}:") else line
        for line in FULL.splitlines()
    )
    with pytest.raises(CaptureFormatError, match="must be one of"):
        _job(text + "\n")


def test_the_enum_error_lists_every_permitted_value() -> None:
    text = "\n".join(
        'employment_type: "Contractor"' if line.startswith("employment_type:") else line
        for line in FULL.splitlines()
    )
    with pytest.raises(CaptureFormatError) as excinfo:
        _job(text + "\n")
    message = str(excinfo.value)
    for member in EmploymentType:
        assert member.value in message


@pytest.mark.parametrize("field", ["job_title", "company_name", "source_platform"])
def test_a_blank_required_field_raises(field: str) -> None:
    text = "\n".join(
        f'{field}: ""' if line.startswith(f"{field}:") else line
        for line in FULL.splitlines()
    )
    with pytest.raises(CaptureFormatError, match="required"):
        _job(text + "\n")


def test_a_duplicate_field_raises() -> None:
    """Keeping one of two captured values would lose source text."""
    with pytest.raises(CaptureFormatError, match="more than once"):
        _job(FULL + '\njob_title: "Something Else"\n')


def test_a_line_that_is_neither_heading_nor_field_raises() -> None:
    with pytest.raises(CaptureFormatError, match="neither a heading nor a labelled field"):
        _job(FULL + "\nstray text with no label\n")


def test_a_blank_job_id_raises() -> None:
    with pytest.raises(CaptureFormatError, match="job_id"):
        _job(FULL, "   ")


# ------------------------------------------------ required technologies, one per line


def test_required_technologies_are_one_per_line() -> None:
    assert _job().required_technologies == ("Python", "RAG", "React.js")


def test_a_comma_separated_line_stays_one_phrase() -> None:
    """Splitting on a comma is a delimiter rule the owner has not approved.

    It would also break A-7: "X, Y, or equivalent" is one any-of slot, and splitting would make
    it three, including a junk "or equivalent" that can never match. A comma-separated line
    therefore arrives as one phrase and will not match, which is visible rather than silent.
    """
    text = FULL.replace("  Python\n  RAG\n  React.js", "  Python, FastAPI")
    assert _job(text).required_technologies == ("Python, FastAPI",)


def test_a_bulleted_line_keeps_its_bullet() -> None:
    text = FULL.replace("  Python\n  RAG\n  React.js", "  - Python")
    assert _job(text).required_technologies == ("- Python",)


# ------------------------------------------------------ D-9: contact cannot survive


def test_recruiter_contact_is_discarded() -> None:
    """D-9. The capture carries it; no destination field exists, so it cannot be stored."""
    assert "public_recruiter_or_contact" in DISCARDED_FIELDS
    assert "someone@invented.example" in FULL
    job = _job()
    assert "someone@invented.example" not in job.model_dump_json()


def test_no_discarded_field_reaches_the_model() -> None:
    job = _job()
    dumped = job.model_dump_json()
    for phrase in ("An invented company.", "Invented listing body.", "Invented capture used"):
        assert phrase not in dumped, f"{phrase!r} survived import"


def test_the_model_still_has_no_contact_field() -> None:
    from vetted.core.domain.job import CompanyFacts, NormalizedJob

    for model in (NormalizedJob, CompanyFacts):
        for field in model.model_fields:
            assert "contact" not in field.lower()
            assert "email" not in field.lower()
            assert "phone" not in field.lower()


# ------------------------------------------------------------------ no I/O, no guessing


def test_the_ingest_package_performs_no_io(src_dir: Path) -> None:
    package = src_dir / "ingest"
    for path in sorted(package.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in (".open(", "read_text", "Path(", "os.environ", "getenv", "input("):
            assert token not in text, f"{path.name} performs I/O via {token!r}"


def test_the_ingest_package_imports_no_io_module(src_dir: Path) -> None:
    banned = {"pathlib", "os", "io", "subprocess", "shutil", "glob", "urllib", "socket", "yaml"}
    package = src_dir / "ingest"
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots = {node.module.split(".")[0]}
            else:
                continue
            assert not roots & banned, f"{path.name} imports {sorted(roots & banned)}"
