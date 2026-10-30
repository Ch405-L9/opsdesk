"""Tracked files must not carry personal data, home paths, or tax identifiers.

Extends job_hunter's sanitized-defaults check to every tracked text file.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\d)(?:\+1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)")
HOME_PATH = re.compile(r"/home/[a-z_][a-z0-9_-]*/|/Users/[A-Za-z]")
TAX_ID = re.compile(r"(?<!\d)\d{2}-\d{7}(?!\d)")
RESERVED_EMAIL_DOMAINS = ("example.com", "example.org", "example.net", ".example", ".test", ".invalid")
TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".toml", ".ini", ".txt", ".json", ".example", ""}


def _tracked_files(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=repo_root, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return [p for p in repo_root.rglob("*") if p.is_file() and ".git" not in p.parts]
    return [repo_root / line for line in result.stdout.splitlines() if line]


def _text_files(repo_root: Path) -> list[Path]:
    files = []
    for path in _tracked_files(repo_root):
        if path.suffix in TEXT_SUFFIXES and path.is_file() and "fixtures" not in path.parts:
            files.append(path)
    return files


def test_no_real_email_addresses(repo_root: Path) -> None:
    for path in _text_files(repo_root):
        found = set(EMAIL.findall(path.read_text(encoding="utf-8", errors="ignore")))
        unexpected = {e for e in found if not e.lower().endswith(RESERVED_EMAIL_DOMAINS)}
        assert not unexpected, f"{path} contains email address(es)"


def test_no_phone_numbers(repo_root: Path) -> None:
    for path in _text_files(repo_root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        real = [m for m in PHONE.findall(text) if not re.search(r"\b555\b", m)]
        assert not real, f"{path} contains a phone number (555 numbers are reserved and allowed)"


def test_no_home_directory_paths(repo_root: Path) -> None:
    for path in _text_files(repo_root):
        assert not HOME_PATH.search(path.read_text(encoding="utf-8", errors="ignore")), (
            f"{path} contains a home-directory path"
        )


def test_no_tax_identifiers(repo_root: Path) -> None:
    for path in _text_files(repo_root):
        assert not TAX_ID.search(path.read_text(encoding="utf-8", errors="ignore")), (
            f"{path} contains an EIN-shaped number"
        )
