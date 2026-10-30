"""The local operator runner.

Not a CLI command: the Typer app stays `doctor`-only while
`report_and_cli_score_display_scope` is unresolved. These tests assert the runner writes
nothing, prints in the approved order with the score never leading, and has no import-time
side effects.

Standard input is always synthetic here. No real listing appears in the test suite.
"""

import ast
import io
from pathlib import Path

import pytest

from vetted.core.config.loader import load_assessment_config
from vetted.core.dossier.terms import CandidateTerm
from vetted.core.enums import EvidenceTier
from vetted.core.tools import technology_alignment as runner

T1 = EvidenceTier.TIER_1_VERIFIED_SKILL

SYNTHETIC_TERMS: tuple[CandidateTerm, ...] = (
    CandidateTerm("Python", T1, "Synthetic skills — Sample section"),
    CandidateTerm("React", T1, "Synthetic skills — Sample section"),
)


def _result(required: tuple[str, ...]):
    from vetted.core.assess.scoring import score_technology_alignment

    return score_technology_alignment(
        "synthetic-1", required, SYNTHETIC_TERMS, load_assessment_config()
    )


def _rendered(required: tuple[str, ...]) -> str:
    return runner.format_result(_result(required), "SYNTHETIC_DOSSIER.md", "0.0.0")


# ------------------------------------------------------------------- stdin parsing


def test_one_technology_per_line() -> None:
    assert runner.read_required_technologies("Python\nRAG\n") == ("Python", "RAG")


def test_blank_lines_are_dropped() -> None:
    assert runner.read_required_technologies("\nPython\n\n   \nRAG\n") == ("Python", "RAG")


def test_empty_input_yields_no_slots() -> None:
    assert runner.read_required_technologies("") == ()
    assert runner.read_required_technologies("   \n\n") == ()


@pytest.mark.parametrize(
    "line", ["- Python", "• Python", "Python,", "* Python", "1. Python"]
)
def test_decoration_is_never_stripped(line: str) -> None:
    """A-6 permits only NFC, casefold, whitespace collapse, and trim.

    A decorated line stays decorated, so it will not match. That is the honest behaviour, and
    the runner prints such phrases with repr() so the artifact is visible.
    """
    assert runner.read_required_technologies(line) == (line,)


def test_a_comma_separated_line_is_not_split() -> None:
    """Splitting on commas would be a new delimiter rule the owner has not approved."""
    assert runner.read_required_technologies("Python, RAG") == ("Python, RAG",)


# ------------------------------------------------------------------ output ordering


def test_the_score_is_not_in_the_first_line() -> None:
    """C-5: the score is never a headline."""
    first = _rendered(("Python",)).splitlines()[0]
    assert "20.0" not in first
    assert "points" not in first.lower()
    assert "score" not in first.lower()


def test_evidence_and_gaps_precede_the_points() -> None:
    """P-6 order: the map and the gaps are read before the number."""
    text = _rendered(("Python", "Weaviate"))
    assert text.index("Evidence-tier map") < text.index("Gaps")
    assert text.index("Gaps") < text.index("Dimension points")


def test_the_points_line_states_its_scope_and_exactness() -> None:
    text = _rendered(("Python",))
    assert "1 of 9 dimensions" in text
    assert "exact and unrounded" in text
    assert "not a match score" in text


def test_no_verdict_value_is_emitted() -> None:
    """Ruling 2: no classification or recommendation value may be displayed as an outcome.

    The zero-slot explanation names AVOID and DO_NOT_APPLY in order to say they cannot follow
    from a zero here (C-3). That sentence is removed before the check, so the test measures
    emitted verdicts rather than the prose that rules them out.
    """
    from vetted.core.enums import MatchClassification, Recommendation

    explanatory = "can never on its\n  own produce AVOID or DO_NOT_APPLY."
    for required in (("Python",), ("Weaviate",), ()):
        text = _rendered(required).replace(explanatory, "")
        for value in (
            *(member.value for member in MatchClassification),
            *(member.value for member in Recommendation),
        ):
            assert value not in text, f"{value} was emitted for {required}"


def test_the_absence_of_a_total_score_is_stated_outright() -> None:
    """A reader must not have to infer that the number is partial."""
    text = _rendered(("Python",))
    assert "No total score exists." in text
    assert "Eight dimensions" in text


def test_the_printed_gate_size_tracks_the_constant() -> None:
    """A hard-coded count went stale the moment the gate grew. It is now computed.

    The footer said "five policy keys" after six allocation keys were added, making the output
    quietly wrong. This test owns that drift.
    """
    from vetted.core.config.schema import REQUIRED_UNRESOLVED_POLICY_KEYS

    text = _rendered(("Python",))
    assert f"{len(REQUIRED_UNRESOLVED_POLICY_KEYS)} policy keys remain" in text
    assert "five policy keys" not in text


def test_points_are_displayed_unrounded() -> None:
    """20 × 1.00 / 3 is 6.666..., and must print in full. Formatting would be rounding."""
    text = _rendered(("Python", "Weaviate", "Pinecone"))
    assert repr(20 * 1.0 / 3) in text
    assert "6.67" not in text


def test_the_formula_is_shown() -> None:
    text = _rendered(("Python", "Weaviate"))
    assert "20 × 1.0 / 2 = 10.0" in text


def test_zero_slots_explains_itself_without_blaming_the_candidate() -> None:
    """C-3: absent listing information can never on its own produce AVOID."""
    text = _rendered(())
    assert "no required technology slots" in text
    assert "not candidate unsuitability" in text
    assert "AVOID or DO_NOT_APPLY" in text


def test_provenance_is_disclosed() -> None:
    text = _rendered(("Python",))
    assert "SYNTHETIC_DOSSIER.md" in text
    assert "read-only" in text


def test_the_gap_names_the_only_flag_it_raises() -> None:
    assert "REQUIRED_SKILL_GAP" in _rendered(("Weaviate",))


def test_unrecognized_terms_are_surfaced_for_review() -> None:
    text = _rendered(("Weaviate",))
    assert "Unrecognized terms, for owner review" in text
    assert "'Weaviate'" in text
    assert "stayed in the denominator" in text


def test_the_display_name_is_shown_not_the_listing_spelling() -> None:
    text = runner.format_result(
        _result(("React.js",)), "SYNTHETIC_DOSSIER.md", "0.0.0"
    )
    assert "\n  React\n" in text
    assert "listing said        'React.js'" in text


# ------------------------------------------------------------------ safety properties


def test_main_returns_zero_on_input(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("Python\n"))
    assert runner.main() == 0
    assert "Evidence-tier map" in capsys.readouterr().out


def test_main_returns_zero_on_empty_input(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert runner.main() == 0
    assert "no required technology slots" in capsys.readouterr().out


def test_a_tty_prints_usage_and_does_not_block(monkeypatch, capsys) -> None:
    """The owner ruled exit 0, and doctor set the precedent against deliberate failure."""

    class _Tty(io.StringIO):
        def isatty(self) -> bool:
            return True

        def read(self, *args: object) -> str:  # pragma: no cover - must never be reached
            raise AssertionError("a TTY run must not read stdin")

    monkeypatch.setattr("sys.stdin", _Tty())
    assert runner.main() == 0
    out = capsys.readouterr().out
    assert "Reads one required technology per line" in out
    assert "not a match score" in out


def test_the_runner_writes_no_file() -> None:
    source = (
        Path(runner.__file__).read_text(encoding="utf-8")
        + Path(runner.__file__).with_name("__init__.py").read_text(encoding="utf-8")
    )
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
    """The suite imports every careerops module. A top-level stdin read would hang it."""
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":' in source
    tree = ast.parse(source)
    for node in tree.body:
        assert isinstance(
            node,
            (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef, ast.Assign, ast.If, ast.Expr),
        ), f"unexpected top-level statement: {type(node).__name__}"
        if isinstance(node, ast.Expr):
            assert isinstance(node.value, ast.Constant), "top-level expression must be a docstring"
