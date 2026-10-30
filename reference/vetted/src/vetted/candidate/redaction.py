"""PII redaction helpers for terminal and report output."""

from __future__ import annotations

import re

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+?1[-. ]?)?(?:\(?\d{3}\)?[-. ]?)\d{3}[-. ]?\d{4}(?!\w)"
)
URL_PATTERN = re.compile(r"https?://[^\s<>()]+", flags=re.IGNORECASE)


def redact_pii(value: str, show_pii: bool = False) -> str:
    """Redact common PII unless local display was explicitly requested."""
    if show_pii:
        return value

    redacted = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
    redacted = PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)
    return URL_PATTERN.sub("[REDACTED_URL]", redacted)
