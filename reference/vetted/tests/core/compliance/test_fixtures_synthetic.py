"""Every committed fixture is invented.

No real contact detail, no real captured posting, and no real company appears in the test
suite (D-12, PROJECT_GUARDRAILS.md data minimization).
"""

import re
from pathlib import Path

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\d)(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}(?!\d)")
URL = re.compile(r"https?://")

REAL_WORLD_TOKENS = (
    "badgrtech",
    "anthonygrant",
    "ch405-l9",
    "uveye",
    "hotsauce",
    "source support",
    "proton.me",
    "linkedin.com",
    "github.com",
    "wellfound.com",
)


TEXT_SUFFIXES = {".py", ".md", ".json", ".yaml", ".yml", ".txt"}


def _fixture_files(repo_root: Path) -> list[Path]:
    """Committed fixture files only. Build artifacts are not committed."""
    root = repo_root / "tests" / "core" / "fixtures"
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix in TEXT_SUFFIXES
    )


def test_fixtures_exist(repo_root: Path) -> None:
    assert _fixture_files(repo_root)


def test_no_email_addresses_in_fixtures(repo_root: Path) -> None:
    for path in _fixture_files(repo_root):
        assert not EMAIL.search(path.read_text(encoding="utf-8")), f"{path} contains an email"


def test_no_phone_numbers_in_fixtures(repo_root: Path) -> None:
    for path in _fixture_files(repo_root):
        assert not PHONE.search(path.read_text(encoding="utf-8")), f"{path} contains a phone"


def test_no_urls_in_fixtures(repo_root: Path) -> None:
    for path in _fixture_files(repo_root):
        assert not URL.search(path.read_text(encoding="utf-8")), f"{path} contains a URL"


def test_no_real_world_identifiers_in_fixtures(repo_root: Path) -> None:
    for path in _fixture_files(repo_root):
        text = path.read_text(encoding="utf-8").lower()
        for token in REAL_WORLD_TOKENS:
            assert token not in text, f"{path} references real-world entity {token!r}"


def test_no_real_captures_committed(repo_root: Path) -> None:
    """Only the two synthetic captures may exist."""
    captures = sorted(
        p.name
        for p in (repo_root / "tests" / "core" / "fixtures" / "captures").iterdir()
        if p.is_file()
    )
    assert captures == [
        "synthetic_listing_minimal.md",
        "synthetic_listing_strong_match.md",
    ]


def test_no_data_directory_is_committed(repo_root: Path) -> None:
    """D-12: local data never enters the repository."""
    for name in ("data", "captures", "reports", "logs"):
        assert not (repo_root / name).exists(), f"{name}/ must not exist in the repository"
