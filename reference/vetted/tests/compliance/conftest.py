"""Shared paths for repository-wide compliance checks."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def src_dir() -> Path:
    return REPO_ROOT / "src" / "vetted"
