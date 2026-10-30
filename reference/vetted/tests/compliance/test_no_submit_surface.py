"""The package must contain no way to submit, upload, log in, or drive a browser.

Adapted from careerops-local compliance tests. These checks read the source itself, so a
future change cannot quietly reintroduce an action surface.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

BANNED_IMPORTS = {
    "browser_use",
    "playwright",
    "selenium",
    "pyautogui",
    "mechanize",
    "requests_html",
}
BANNED_NAME_FRAGMENTS = ("form_filler", "auto_apply", "submit_application", "upload_resume")
CLICK_CALL = re.compile(r"\.click\(")
CREDENTIAL_FIELD = re.compile(r"\b(password|passwd|credential|session_cookie|login_token)\b")


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_no_browser_or_automation_imports(src_dir: Path) -> None:
    for path in sorted(src_dir.rglob("*.py")):
        offending = _imported_roots(path) & BANNED_IMPORTS
        assert not offending, f"{path} imports {sorted(offending)}"


def test_no_click_calls(src_dir: Path) -> None:
    for path in sorted(src_dir.rglob("*.py")):
        assert not CLICK_CALL.search(path.read_text(encoding="utf-8")), f"{path} calls .click()"


def test_no_submit_or_upload_helpers(src_dir: Path) -> None:
    for path in sorted(src_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8").lower()
        for fragment in BANNED_NAME_FRAGMENTS:
            assert fragment not in text, f"{path} mentions {fragment}"


def test_no_credential_fields_in_settings(src_dir: Path) -> None:
    text = (src_dir / "settings.py").read_text(encoding="utf-8").lower()
    assert not CREDENTIAL_FIELD.search(text), "settings.py declares a credential-like field"


def test_no_browser_dependencies_declared(repo_root: Path) -> None:
    text = (repo_root / "pyproject.toml").read_text(encoding="utf-8").lower()
    for name in ("playwright", "selenium", "browser-use", "browser_use"):
        assert name not in text, f"pyproject.toml declares {name}"
