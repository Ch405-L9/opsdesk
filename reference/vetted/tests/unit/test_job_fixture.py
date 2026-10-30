from pathlib import Path

import pytest

from vetted.jobs.fixture import load_job_fixture


def test_load_job_fixture_loads_completed_mapping(tmp_path: Path) -> None:
    source_path = tmp_path / "job.yaml"
    source_path.write_text(
        "title: QA Lead\ncompany: Example Games\n",
        encoding="utf-8",
    )

    fixture = load_job_fixture(tmp_path)

    assert fixture is not None
    assert fixture.title == "QA Lead"
    assert fixture.company == "Example Games"
    assert fixture.source_path == source_path


def test_load_job_fixture_returns_none_when_no_completed_fixture_exists(
    tmp_path: Path,
) -> None:
    assert load_job_fixture(tmp_path) is None


def test_load_job_fixture_ignores_template_only_directory(
    tmp_path: Path,
) -> None:
    (tmp_path / "job_metadata.template.yaml").write_text(
        "template placeholder content\n",
        encoding="utf-8",
    )

    assert load_job_fixture(tmp_path) is None


def test_load_job_fixture_rejects_multiple_completed_fixtures(
    tmp_path: Path,
) -> None:
    (tmp_path / "one.yaml").write_text(
        "title: First role\ncompany: First company\n",
        encoding="utf-8",
    )
    (tmp_path / "two.yaml").write_text(
        "title: Second role\ncompany: Second company\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Expected exactly one job YAML fixture"):
        load_job_fixture(tmp_path)
