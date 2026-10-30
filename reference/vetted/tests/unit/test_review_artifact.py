from vetted.review.artifact import render_review_artifact
from vetted.workflow.draft import DraftArtifact


def test_render_review_artifact_marks_review_required() -> None:
    draft = DraftArtifact(
        evidence_record_count=1,
        status="review_required",
        submission_statement=(
            "NO APPLICATION HAS BEEN SUBMITTED. "
            "HUMAN REVIEW AND MANUAL SUBMISSION ARE REQUIRED."
        ),
    )

    artifact = render_review_artifact(draft)

    assert artifact["artifact_type"] == "local_review_draft"
    assert artifact["review_required"] is True
    assert artifact["evidence_record_count"] == 1
    assert artifact["status"] == "review_required"
