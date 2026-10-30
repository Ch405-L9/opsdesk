"""`vetted assess` ranks captures against a dossier and never submits anything."""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from vetted.cli import app

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = REPO_ROOT / "config" / "examples"


def _env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setenv("ALLOW_SUBMIT", "false")


def test_assess_prints_a_report_and_the_no_submit_line(monkeypatch, tmp_path: Path) -> None:
    _env(monkeypatch, tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "assess",
            str(EXAMPLES / "capture.example.md"),
            "--dossier",
            str(EXAMPLES / "dossier.example.yaml"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Python" in result.output
    assert "NO APPLICATION HAS BEEN SUBMITTED" in result.output


def test_assess_ranks_two_captures(monkeypatch, tmp_path: Path) -> None:
    _env(monkeypatch, tmp_path)
    capture = str(EXAMPLES / "capture.example.md")
    result = CliRunner().invoke(
        app, ["assess", capture, capture, "--dossier", str(EXAMPLES / "dossier.example.yaml")]
    )
    assert result.exit_code == 0, result.output
    assert "Could not be imported" not in result.output


def test_assess_reports_a_bad_dossier(monkeypatch, tmp_path: Path) -> None:
    _env(monkeypatch, tmp_path)
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({"name": "x", "email": "someone@example.com"}), encoding="utf-8")
    result = CliRunner().invoke(
        app, ["assess", str(EXAMPLES / "capture.example.md"), "--dossier", str(bad)]
    )
    assert result.exit_code == 2
    assert "Dossier problem" in result.output
