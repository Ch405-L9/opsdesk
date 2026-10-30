"""Tests for fail-closed application settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vetted.settings import Settings


def test_allow_submit_must_be_explicitly_false() -> None:
    """Missing ALLOW_SUBMIT is unsafe and must fail."""
    with pytest.raises(ValidationError, match="explicitly set to false"):
        Settings(allow_submit=None)


def test_allow_submit_true_is_rejected() -> None:
    """Enabled submission must fail configuration validation."""
    with pytest.raises(ValidationError, match="explicitly set to false"):
        Settings(allow_submit=True)


def test_allow_submit_false_is_accepted() -> None:
    """Explicit false is the only valid submission configuration."""
    settings = Settings(allow_submit=False)
    assert settings.allow_submit is False
