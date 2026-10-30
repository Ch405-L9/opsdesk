"""Tests for permanent no-submit and fill-confirmation safeguards."""

from __future__ import annotations

import pytest

from vetted.exceptions import SafetyViolationError
from vetted.safety import (
    NO_SUBMIT_STATEMENT,
    enforce_no_submit,
    require_interactive_fill_confirmation,
)
from vetted.settings import Settings


def test_required_no_submit_statement_is_exact() -> None:
    """Runtime reports must include the required policy statement."""
    assert NO_SUBMIT_STATEMENT == (
        "NO APPLICATION HAS BEEN SUBMITTED. HUMAN REVIEW AND MANUAL SUBMISSION ARE REQUIRED."
    )


def test_explicit_false_submission_setting_passes() -> None:
    """Submission safety accepts only the false state."""
    settings = Settings(allow_submit=False)
    enforce_no_submit(settings)


def test_fill_requires_allow_fill() -> None:
    """Confirmation cannot override a disabled fill setting."""
    settings = Settings(allow_submit=False, allow_fill=False)

    with pytest.raises(SafetyViolationError, match="ALLOW_FILL"):
        require_interactive_fill_confirmation(settings, confirm_fill=True)


def test_fill_requires_explicit_confirmation() -> None:
    """Configured filling still requires a per-run confirmation."""
    settings = Settings(allow_submit=False, allow_fill=True)

    with pytest.raises(SafetyViolationError, match="confirm-fill"):
        require_interactive_fill_confirmation(settings, confirm_fill=False)
