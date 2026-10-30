"""Multi-listing comparison.

Every capture is invented and built inline. Ranking is by technology alignment only, because
that is the one dimension with an approved allocation rule.
"""

import ast
import io
from pathlib import Path

import pytest

from vetted.core.config.loader import load_assessment_config
from vetted.core.ingest.capture import parse_capture
from vetted.core.tools import listing_report as runner


def _capture(
    title: str = "Invented Role",
    company: str = "Invented Co",
    url: str = "UNKNOWN",
    arrangement: str = "US_REMOTE",
    relocation: str = "NOT_MENTIONED",
    location: str = "Remote, United States",
    salary: str = "110000",
    technologies: str = "Python",
) -> str:
    tech_block = "\n".join(f"  {line}" for line in technologies.splitlines())
    return f"""---
source_platform: wellfound
source_url: "{url}"
---

job_title: "{title}"
company_name: "{company}"
employment_type: "FULL_TIME"
work_arrangement: "{arrangement}"
relocation_status: "{relocation}"
location_text: "{location}"
base_salary_min_usd: {salary}
required_technologies: |
{tech_block}
"""


@pytest.fixture(scope="module")
def config():
    return load_assessment_config()


def _run(text: str, monkeypatch, capsys) -> str:
    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    assert runner.main() == 0
    return capsys.readouterr().out


def _position(config, **kwargs) -> str:
    job = parse_capture(_capture(**kwargs), "x")
    return runner.salary_position(
        job,
        config.compensation.salary_targets,
        config.compensation.regional_price_parity,
    )


# --------------------------------------------------------------------- splitting


def test_captures_split_on_the_separator() -> None:
    text = _capture(title="A") + f"\n{runner.SEPARATOR}\n" + _capture(title="B")
    blocks = runner.split_captures(text)
    assert len(blocks) == 2
    assert '"A"' in blocks[0] and '"B"' in blocks[1]


def test_a_single_capture_needs_no_separator() -> None:
    assert len(runner.split_captures(_capture())) == 1


def test_empty_input_yields_no_blocks() -> None:
    assert runner.split_captures("") == []
    assert runner.split_captures("===\n===\n") == []


# ----------------------------------------------------------- salary, the soft floor


def test_a_salary_under_the_floor_is_shown_not_dropped(config) -> None:
    """Owner decision 2026-09-26: the floor is soft."""
    text = _position(config, salary="65000")
    assert "below your 70,000 floor" in text
    assert "shown, not dropped" in text


def test_a_salary_under_the_soft_minimum_is_the_owners_call(config) -> None:
    assert "under your soft minimum — your call" in _position(config, salary="79000")


def test_a_salary_above_market_says_so(config) -> None:
    assert "at or above market target" in _position(config, salary="150000")


def test_absent_salary_is_missing_evidence_not_rejection(config) -> None:
    text = _position(config, salary='"UNKNOWN"')
    assert "not stated" in text
    assert "never a rejection" in text


# ------------------------------------------------- cost of living, relocation only


def test_a_remote_listing_is_never_cost_of_living_adjusted(config) -> None:
    """The candidate stays in Georgia and spends at Georgia prices."""
    text = _position(config, arrangement="US_REMOTE", location="San Francisco, CA", salary="135000")
    assert "cost of living" not in text
    assert "135,000 stated" in text


def test_an_onsite_listing_is_adjusted_to_home_purchasing_power(config) -> None:
    text = _position(
        config, arrangement="ON_SITE", relocation="REQUIRED", location="San Francisco, CA", salary="135000"
    )
    assert "CA cost of living" in text
    assert "GA equivalent" in text


def test_an_unverified_state_gets_no_adjustment(config) -> None:
    """No interpolated guesses. Colorado has no individually verified parity yet."""
    text = _position(
        config, arrangement="ON_SITE", relocation="REQUIRED", location="Denver, CO", salary="135000"
    )
    assert "no published parity" in text


def test_a_cheaper_state_reads_as_upside(config) -> None:
    """North Carolina is cheaper than Georgia, so the same salary is worth more there."""
    text = _position(
        config, arrangement="ON_SITE", relocation="REQUIRED", location="Raleigh, NC", salary="135000"
    )
    assert "NC cost of living" in text
    assert "137," in text


def test_a_state_code_is_read_only_in_the_city_state_position(config) -> None:
    """Matching any uppercase token would read "travel OK" as Oklahoma."""
    text = _position(
        config,
        arrangement="ON_SITE",
        relocation="REQUIRED",
        location="Somewhere remote travel OK required",
        salary="135000",
    )
    assert "no published parity" in text


def test_a_salary_range_is_displayed_in_full(config) -> None:
    """The owner wants high-end offers surfaced, not hidden behind their floor."""
    job = parse_capture(
        _capture(salary="90000").replace(
            "base_salary_min_usd: 90000",
            "base_salary_min_usd: 90000\nbase_salary_max_usd: 150000",
        ),
        "x",
    )
    text = runner.salary_position(
        job,
        config.compensation.salary_targets,
        config.compensation.regional_price_parity,
    )
    assert "90,000-150,000 stated" in text


def test_an_ambiguous_location_gets_no_adjustment(config) -> None:
    """Two known state codes in one string is ambiguous, so nothing is assumed."""
    text = _position(
        config, arrangement="ON_SITE", relocation="REQUIRED", location="CA or NJ office", salary="135000"
    )
    assert "no published parity" in text


# ------------------------------------------------------ category substitution in report


def test_a_core_language_gap_is_the_headline(monkeypatch, capsys) -> None:
    """A Rust role you cannot fill outranks softer gaps in the summary."""
    out = _run(_capture(technologies="Rust\nPython"), monkeypatch, capsys)
    assert "CORE_LANGUAGE_GAP" in out
    assert "top gap        Rust" in out


def test_a_language_miss_does_not_erase_a_language_hit(monkeypatch, capsys) -> None:
    out = _run(_capture(technologies="Rust\nPython"), monkeypatch, capsys)
    assert "Python (EXACT)" in out
    assert "10.0 of 20" in out


# ----------------------------------------------------------------- ranking and links


def test_listings_are_ranked_by_technology_points(monkeypatch, capsys) -> None:
    weak = _capture(title="Weak Role", technologies="Rust")
    strong = _capture(title="Strong Role", technologies="Python\nFastAPI")
    out = _run(f"{weak}\n{runner.SEPARATOR}\n{strong}", monkeypatch, capsys)
    assert out.index("Strong Role") < out.index("Weak Role")


def test_the_link_is_shown_when_captured(monkeypatch, capsys) -> None:
    out = _run(_capture(url="https://example.invalid/jobs/1"), monkeypatch, capsys)
    assert "https://example.invalid/jobs/1" in out


def test_a_missing_link_says_so(monkeypatch, capsys) -> None:
    assert "not captured" in _run(_capture(), monkeypatch, capsys)


def test_the_ranking_states_what_it_ranks_on(monkeypatch, capsys) -> None:
    out = _run(_capture(), monkeypatch, capsys)
    assert "one of nine" in out
    assert "not a match score, classification, or recommendation" in out
    assert "Read the" in out and "gaps before the numbers" in out


def test_a_malformed_capture_is_reported_and_the_rest_still_ranks(
    monkeypatch, capsys
) -> None:
    bad = _capture(title="Bad Role", salary='"$110,000"')
    good = _capture(title="Good Role")
    out = _run(f"{bad}\n{runner.SEPARATOR}\n{good}", monkeypatch, capsys)
    assert "could not be imported" in out
    assert "plain integer" in out
    assert "Good Role" in out


def test_a_tty_prints_usage(monkeypatch, capsys) -> None:
    class _Tty(io.StringIO):
        def isatty(self) -> bool:
            return True

        def read(self, *args: object) -> str:  # pragma: no cover
            raise AssertionError("a TTY run must not read stdin")

    monkeypatch.setattr("sys.stdin", _Tty())
    assert runner.main() == 0
    assert "separated by a line containing only" in capsys.readouterr().out


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


def test_no_verdict_value_is_emitted(monkeypatch, capsys) -> None:
    from vetted.core.enums import MatchClassification, Recommendation

    out = _run(_capture(technologies="Rust\nPython"), monkeypatch, capsys)
    for value in (
        *(m.value for m in MatchClassification),
        *(m.value for m in Recommendation),
    ):
        assert value not in out
