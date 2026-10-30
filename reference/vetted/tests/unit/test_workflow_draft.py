from pathlib import Path

from vetted.safety import NO_SUBMIT_STATEMENT
from vetted.settings import Settings
from vetted.workflow.draft import build_local_draft


def test_build_local_draft_counts_evidence_and_requires_review(
    tmp_path: Path,
    monkeypatch,
) -> None:
    evidence_root = tmp_path / "candidate" / "evidence"
    evidence_root.mkdir(parents=True)

    (evidence_root / "record.yaml").write_text(
        """
evidence_id: EV-TEST-001
category: applied_ai_rag
factual_statement: Built and validated a local test draft workflow.
approved_for_external_use: true
tags:
  - python
  - testing
source_pages:
  - 1
source_excerpt: Verified local test evidence.
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("ALLOW_SUBMIT", "false")
    settings = Settings(
        candidate_data_path=tmp_path / "candidate",
        job_data_path=tmp_path / "job",
    )

    draft = build_local_draft(settings)

    assert draft.evidence_record_count == 1
    assert draft.status == "review_required"
    assert draft.submission_statement == NO_SUBMIT_STATEMENT
