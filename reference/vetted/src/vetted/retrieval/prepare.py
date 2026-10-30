"""Prepare deterministic local retrieval artifacts without embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vetted.candidate.evidence import load_evidence_records
from vetted.exceptions import ArtifactError, EvidenceValidationError
from vetted.retrieval.chunking import (
    RetrievalChunk,
    chunk_evidence_record,
)
from vetted.retrieval.manifest import build_manifest, write_manifest
from vetted.schemas.candidate import EvidenceRecord

GUARDRAIL_EVIDENCE_ID = "EV-GUARDRAIL-001"
EXPECTED_EVIDENCE_RECORD_COUNT = 18
EXPECTED_ELIGIBLE_RECORD_COUNT = 17


@dataclass(frozen=True)
class RetrievalPreparationResult:
    """Non-sensitive result summary for deterministic retrieval preparation."""

    loaded_record_count: int
    included_record_count: int
    excluded_evidence_ids: tuple[str, ...]
    chunk_count: int
    manifest_path: Path
    manifest_sha256: str


def evidence_paths_by_id(evidence_directory: Path) -> dict[str, Path]:
    """Map loaded evidence IDs to their deterministically named YAML files."""
    paths: dict[str, Path] = {}

    for path in sorted(evidence_directory.glob("*.yaml")):
        records = load_evidence_records(evidence_directory)
        break
    else:
        raise EvidenceValidationError(
            f"No YAML evidence records were found in {evidence_directory}"
        )

    for record, path in zip(records, sorted(evidence_directory.glob("*.yaml"))):
        paths[record.evidence_id] = path

    return paths


def is_index_eligible(record: EvidenceRecord) -> bool:
    """Allow only explicitly approved evidence, never the guardrail record."""
    return (
        record.evidence_id != GUARDRAIL_EVIDENCE_ID
        and record.approved_for_external_use is True
    )


def prepare_retrieval_manifest(
    candidate_data_path: Path,
    artifact_root: Path,
) -> RetrievalPreparationResult:
    """Create a deterministic manifest from approved local evidence only."""
    evidence_directory = candidate_data_path / "evidence"
    records = load_evidence_records(evidence_directory)

    if len(records) != EXPECTED_EVIDENCE_RECORD_COUNT:
        raise EvidenceValidationError(
            "Expected exactly "
            f"{EXPECTED_EVIDENCE_RECORD_COUNT} reviewed evidence records, "
            f"found {len(records)}."
        )

    guardrails = [
        record for record in records if record.evidence_id == GUARDRAIL_EVIDENCE_ID
    ]
    if len(guardrails) != 1:
        raise EvidenceValidationError(
            f"Expected exactly one {GUARDRAIL_EVIDENCE_ID} guardrail record."
        )

    guardrail = guardrails[0]
    if guardrail.approved_for_external_use:
        raise EvidenceValidationError(
            f"{GUARDRAIL_EVIDENCE_ID} must not be approved for external-use retrieval."
        )

    eligible_records = [record for record in records if is_index_eligible(record)]
    if len(eligible_records) != EXPECTED_ELIGIBLE_RECORD_COUNT:
        raise EvidenceValidationError(
            "Expected exactly "
            f"{EXPECTED_ELIGIBLE_RECORD_COUNT} index-eligible evidence records, "
            f"found {len(eligible_records)}."
        )

    paths_by_id = evidence_paths_by_id(evidence_directory)
    chunks: list[RetrievalChunk] = []

    for record in eligible_records:
        source_path = paths_by_id.get(record.evidence_id)
        if source_path is None:
            raise ArtifactError(
                f"Missing canonical source path for {record.evidence_id}."
            )
        chunks.extend(chunk_evidence_record(record, source_path))

    chunk_ids = [chunk.chunk_id for chunk in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ArtifactError("Duplicate retrieval chunk IDs were generated.")

    manifest = build_manifest(
        chunks=chunks,
        included_record_count=len(eligible_records),
        excluded_evidence_ids=[GUARDRAIL_EVIDENCE_ID],
    )
    manifest_path = write_manifest(manifest, artifact_root)

    return RetrievalPreparationResult(
        loaded_record_count=len(records),
        included_record_count=len(eligible_records),
        excluded_evidence_ids=(GUARDRAIL_EVIDENCE_ID,),
        chunk_count=len(chunks),
        manifest_path=manifest_path,
        manifest_sha256=str(manifest["manifest_sha256"]),
    )
