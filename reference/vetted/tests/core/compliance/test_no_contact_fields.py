"""Contact, ownership, and years-of-experience data must be unrepresentable.

Enforces owner decisions D-2, D-4, and D-9 against the model definitions themselves, so a
future field cannot reintroduce them quietly.
"""

import ast
from pathlib import Path

from pydantic import BaseModel

from vetted.core.domain import assessment as assessment_models
from vetted.core.domain import candidate as candidate_models
from vetted.core.domain import job as job_models

CONTACT_TOKENS = (
    "email",
    "phone",
    "mobile",
    "address",
    "street",
    "postal",
    "zip",
    "contact",
    "ssn",
    "dob",
    "date_of_birth",
    "passport",
    "bank",
    "tax",
    "ein",
    "duns",
)
OWNERSHIP_TOKENS = ("owner", "officer", "equity", "shareholder", "member_of_record", "llc_member")
DATE_ARITHMETIC_TOKENS = ("timedelta", "relativedelta", "dateutil")

ALLOWED_YEARS_FIELDS = {"years_of_experience_requirement"}


def _model_fields(module: object) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for attr_name, attr in vars(module).items():
        if isinstance(attr, type) and issubclass(attr, BaseModel) and attr is not BaseModel:
            found.extend((attr_name, field) for field in attr.model_fields)
    return found


ALL_MODULES = (candidate_models, job_models, assessment_models)


def test_no_contact_fields_on_any_domain_model() -> None:
    """D-9."""
    for module in ALL_MODULES:
        for model_name, field in _model_fields(module):
            lowered = field.lower()
            for token in CONTACT_TOKENS:
                assert token not in lowered, f"{model_name}.{field} looks like contact data"


def test_no_ownership_fields_on_any_domain_model() -> None:
    """D-2: business ownership is never modelled."""
    for module in ALL_MODULES:
        for model_name, field in _model_fields(module):
            lowered = field.lower()
            for token in OWNERSHIP_TOKENS:
                assert token not in lowered, f"{model_name}.{field} looks like ownership data"


def test_no_candidate_years_of_experience_field() -> None:
    """D-4: no total-years figure on the candidate side."""
    for model_name, field in _model_fields(candidate_models):
        assert "year" not in field.lower(), f"{model_name}.{field} exposes a years figure"


def test_only_the_listing_may_state_a_years_requirement() -> None:
    """A listing's stated requirement is a listing fact, not a candidate figure."""
    years_fields = {
        field for _, field in _model_fields(job_models) if "year" in field.lower()
    }
    assert years_fields <= ALLOWED_YEARS_FIELDS


def test_no_date_arithmetic_in_source(src_dir: Path) -> None:
    """D-4: experience years are never inferred from job dates."""
    for path in sorted(src_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8").lower()
        for token in DATE_ARITHMETIC_TOKENS:
            assert token not in text, f"{path} references date arithmetic ({token})"


def test_employment_dates_are_opaque_strings() -> None:
    """Dates are display strings, so nothing can subtract them."""
    annotations = candidate_models.EmploymentEvidence.model_fields
    assert annotations["start"].annotation is str
    assert annotations["end"].annotation is str


def test_source_defines_no_date_typed_field(src_dir: Path) -> None:
    for path in sorted(src_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.annotation, ast.Name):
                assert node.annotation.id not in {"date", "datetime"}, f"{path} uses a date type"
