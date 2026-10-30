"""Load local job fixtures for review-only draft preparation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class JobFixture:
    """Minimal local job data used for a review-only draft."""

    title: str
    company: str
    source_path: Path


def load_job_fixture(job_data_path: Path) -> JobFixture | None:
    """Load one completed local job YAML fixture, if one is provided.

    Template YAML files are ignored. This loader does not infer job facts,
    access the network, scrape job pages, or submit applications.
    """
    fixture_files = sorted(
        path
        for path in job_data_path.glob("*.yaml")
        if not path.name.endswith(".template.yaml")
    )

    if not fixture_files:
        return None

    if len(fixture_files) != 1:
        raise ValueError(
            f"Expected exactly one job YAML fixture in {job_data_path}; "
            f"found {len(fixture_files)}."
        )

    source_path = fixture_files[0]
    raw = yaml.safe_load(source_path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise TypeError(f"Job fixture must be a YAML mapping: {source_path}")

    title = raw.get("title") or raw.get("job_title")
    company = raw.get("company") or raw.get("company_name")

    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"Job fixture title is required: {source_path}")

    if not isinstance(company, str) or not company.strip():
        raise ValueError(f"Job fixture company is required: {source_path}")

    return JobFixture(
        title=title.strip(),
        company=company.strip(),
        source_path=source_path,
    )
