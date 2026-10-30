"""Review-only presentation of local draft artifacts."""

from __future__ import annotations

from dataclasses import asdict

from vetted.workflow.draft import DraftArtifact


def render_review_artifact(draft: DraftArtifact) -> dict[str, object]:
    """Return a structured in-memory review artifact without persistent output."""
    return {
        "artifact_type": "local_review_draft",
        "review_required": True,
        **asdict(draft),
    }
