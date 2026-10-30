"""PII-redaction behavior tests."""

from __future__ import annotations

from vetted.candidate.redaction import redact_pii


def test_redact_pii_hides_email_phone_and_url() -> None:
    value = (
        "Contact [candidate@example.com](mailto:candidate@example.com) at 470-555-1234 "
        "or visit [https://example.com/profile](https://example.com/profile)."
    )

    redacted = redact_pii(value)

    assert "candidate@example.com" not in redacted
    assert "470-555-1234" not in redacted
    assert "https://example.com/profile" not in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert "[REDACTED_URL]" in redacted


def test_redact_pii_allows_explicit_local_display() -> None:
    value = "candidate@example.com"

    assert redact_pii(value, show_pii=True) == value
