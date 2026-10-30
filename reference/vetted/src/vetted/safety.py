"""Non-negotiable safety invariants for local application preparation."""

from __future__ import annotations

from vetted.exceptions import SafetyViolationError
from vetted.settings import Settings

NO_SUBMIT_STATEMENT = (
    "NO APPLICATION HAS BEEN SUBMITTED. HUMAN REVIEW AND MANUAL SUBMISSION ARE REQUIRED."
)


def enforce_no_submit(settings: Settings) -> None:
    """Reject any configuration that could enable application submission."""
    if settings.allow_submit is not False:
        raise SafetyViolationError("Submission is permanently disabled.")


def require_interactive_fill_confirmation(
    settings: Settings,
    confirm_fill: bool,
) -> None:
    """Permit field filling only after explicit, safe configuration and confirmation."""
    enforce_no_submit(settings)

    if settings.allow_fill is not True:
        raise SafetyViolationError(
            "ALLOW_FILL must be true before any fill operation is permitted."
        )

    if not confirm_fill:
        raise SafetyViolationError(
            "Field filling requires explicit --confirm-fill confirmation."
        )

