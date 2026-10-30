"""The capture-alignment runner.

Reads a complete capture from stdin, imports it, and prints one dimension. Capture text is
built inline: every listing here is invented.
"""

import ast
import io
from pathlib import Path

from vetted.core.ingest.capture import parse_capture
from vetted.core.tools import capture_alignment as runner

CAPTURE = """---
source_platform: wellfound
---

# Job identity

job_title: "Invented AI Role"
company_name: "Invented Analytics"
company_website: "UNKNOWN"
official_careers_url: "UNKNOWN"

# Work arrangement

employment_type: "FULL_TIME"
work_arrangement: "US_REMOTE"
relocation_status: "NOT_MENTIONED"
location_text: "Remote, United States"
work_authorization_requirements: "Must be authorized"
clearance_requirements: "Secret clearance required"

# Compensation

base_salary_min_usd: 120000

# Role content

years_of_experience: "3+ years"
required_technologies: |
  Python
  RAG
  Weaviate
"""


def _facts(text: str = CAPTURE) -> str:
    return runner.format_capture_facts(parse_capture(text, "synthetic-1"))


# ------------------------------------------------------------- imported facts are shown


def test_every_imported_fact_is_rendered() -> None:
    """This caught a call to a method that does not exist. Rendering must be exercised."""
    facts = _facts()
    for expected in (
        "Invented AI Role",
        "Invented Analytics",
        "FULL_TIME",
        "US_REMOTE",
        "NOT_MENTIONED",
        "Remote, United States",
        "120000",
        "3+ years",
    ):
        assert expected in facts, f"{expected!r} was imported but not displayed"


def test_the_facts_are_labelled_unscored() -> None:
    """Eight dimensions have no allocation rule, so none of these may look like a score."""
    facts = _facts()
    assert "disclosed, not scored" in facts
    assert "no approved allocation rule" in facts


def test_d5_fields_are_never_displayed_as_dimension_inputs() -> None:
    """D-5: authorization and clearance inform hard blockers only, never a dimension score."""
    facts = _facts()
    assert "Must be authorized" not in facts
    assert "Secret clearance required" not in facts
    assert "never a dimension score (D-5)" in facts


def test_changing_only_d5_fields_changes_no_output() -> None:
    other = CAPTURE.replace('"Must be authorized"', '"UNKNOWN"').replace(
        '"Secret clearance required"', '"UNKNOWN"'
    )
    assert _facts() == _facts(other)


# ----------------------------------------------------------------------- end to end


def test_main_scores_a_capture(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(CAPTURE))
    assert runner.main() == 0
    out = capsys.readouterr().out
    assert "Imported listing facts" in out
    assert "Evidence-tier map" in out
    assert "20 × 1.0 / 3" in out


def test_a_malformed_capture_reports_and_does_not_crash(monkeypatch, capsys) -> None:
    bad = CAPTURE.replace("base_salary_min_usd: 120000", 'base_salary_min_usd: "$120,000"')
    monkeypatch.setattr("sys.stdin", io.StringIO(bad))
    assert runner.main() == 0
    out = capsys.readouterr().out
    assert "could not be imported" in out
    assert "plain integer" in out
    assert "Evidence-tier map" not in out


def test_a_tty_prints_usage(monkeypatch, capsys) -> None:
    class _Tty(io.StringIO):
        def isatty(self) -> bool:
            return True

        def read(self, *args: object) -> str:  # pragma: no cover
            raise AssertionError("a TTY run must not read stdin")

    monkeypatch.setattr("sys.stdin", _Tty())
    assert runner.main() == 0
    assert "complete capture" in capsys.readouterr().out


def test_a_comma_separated_line_arrives_as_one_unmatched_phrase(monkeypatch, capsys) -> None:
    """Splitting on a comma is not an approved rule, and would break any-of grouping.

    A-7 makes "X, Y, or equivalent" one any-of slot. Comma splitting would turn it into three
    slots including a junk "or equivalent" that can never match, so the phrase is left whole.
    The consequence is visible: one slot, no match, zero points.
    """
    text = CAPTURE.replace("  Python\n  RAG\n  Weaviate", "  Python, RAG")
    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    assert runner.main() == 0
    out = capsys.readouterr().out
    assert "'Python, RAG'" in out
    assert "20 × 0.0 / 1 = 0.0" in out


def test_an_any_of_phrase_is_one_slot_not_three(monkeypatch, capsys) -> None:
    """A-7, asserted as behaviour rather than only as documentation."""
    text = CAPTURE.replace(
        "  Python\n  RAG\n  Weaviate", "  Python\n  ChromaDB, Weaviate, or equivalent"
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    assert runner.main() == 0
    out = capsys.readouterr().out
    assert "slots after normalization and deduplication: 2" in out
    assert "'ChromaDB, Weaviate, or equivalent'" in out
    assert "'or equivalent'" not in out, "the any-of phrase was split into separate slots"
    assert "'ChromaDB'" not in out


def test_the_strong_match_fixture_now_scores_the_full_dimension(
    monkeypatch, capsys, repo_root: Path
) -> None:
    """The fixture was corrected to one technology per line, matching its name.

    It previously wrote "Python, FastAPI" on one line and scored 0.0 of 20, which made a file
    called synthetic_listing_strong_match misleading.
    """
    text = (
        repo_root / "tests" / "core" / "fixtures" / "captures" / "synthetic_listing_strong_match.md"
    ).read_text(encoding="utf-8")
    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    assert runner.main() == 0
    out = capsys.readouterr().out
    assert "20 × 2.0 / 2 = 20.0" in out
    assert "Gaps\n  None." in out


# ------------------------------------------------------------------ safety properties


def test_the_runner_writes_no_file() -> None:
    source = Path(runner.__file__).read_text(encoding="utf-8")
    for token in ("open(", "write_text", "mkdir", "Path(", "os.environ", "getenv"):
        assert token not in source, f"the runner touches the filesystem via {token!r}"


def test_the_runner_imports_no_banned_module() -> None:
    banned = {"os", "shutil", "glob", "subprocess", "pathlib", "urllib", "socket", "typer"}
    tree = ast.parse(Path(runner.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots = {node.module.split(".")[0]}
        else:
            continue
        assert not roots & banned, f"the runner imports {sorted(roots & banned)}"


def test_all_execution_is_guarded_by_main() -> None:
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":' in source
    for node in ast.parse(source).body:
        assert isinstance(
            node,
            (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef, ast.Assign, ast.If, ast.Expr),
        ), f"unexpected top-level statement: {type(node).__name__}"


def test_no_captures_directory_is_created(repo_root: Path) -> None:
    """The capture arrives on stdin, so no path is accepted and no directory appears."""
    for name in ("data", "captures", "reports", "logs"):
        assert not (repo_root / name).exists()
