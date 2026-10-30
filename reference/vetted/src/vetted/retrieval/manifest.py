"""Deterministic manifest generation for local retrieval preparation."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from vetted.exceptions import ArtifactError
from vetted.retrieval.chunking import (
    CHUNKING_ALGORITHM,
    MAX_CHARS,
    OVERLAP_CHARS,
    RetrievalChunk,
)

MANIFEST_FILENAME = "evidence_manifest.json"
MANIFEST_SCHEMA_VERSION = 1


def artifact_manifest_path(artifact_root: Path) -> Path:
    """Return the only approved local retrieval-manifest destination."""
    return artifact_root / "retrieval" / MANIFEST_FILENAME


def ensure_approved_manifest_path(path: Path, artifact_root: Path) -> None:
    """Reject manifest output outside the configured local artifact root."""
    approved_root = (artifact_root / "retrieval").resolve()
    resolved_path = path.resolve()

    if resolved_path.parent != approved_root:
        raise ArtifactError(
            f"Retrieval manifest output must be directly inside {approved_root}."
        )

    if resolved_path.name != MANIFEST_FILENAME:
        raise ArtifactError(f"Retrieval manifest filename must be {MANIFEST_FILENAME}.")


def canonical_json_bytes(payload: dict[str, object]) -> bytes:
    """Serialize JSON deterministically for integrity hashing."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def build_manifest(
    chunks: list[RetrievalChunk],
    included_record_count: int,
    excluded_evidence_ids: list[str],
) -> dict[str, object]:
    """Build a deterministic, integrity-addressed retrieval manifest."""
    chunk_ids = [chunk.chunk_id for chunk in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ArtifactError("Duplicate retrieval chunk IDs were generated.")

    payload: dict[str, object] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generator": "vetted",
        "chunking": {
            "algorithm": CHUNKING_ALGORITHM,
            "max_chars": MAX_CHARS,
            "overlap_chars": OVERLAP_CHARS,
        },
        "source": {
            "evidence_directory": "data/candidate/evidence",
            "included_record_count": included_record_count,
            "excluded_evidence_ids": sorted(excluded_evidence_ids),
        },
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "evidence_id": chunk.evidence_id,
                "source_filename": chunk.source_filename,
                "chunk_index": chunk.chunk_index,
                "char_count": chunk.char_count,
                "sha256": chunk.sha256,
                "text": chunk.text,
            }
            for chunk in chunks
        ],
    }

    manifest_sha256 = sha256(canonical_json_bytes(payload)).hexdigest()
    return {**payload, "manifest_sha256": manifest_sha256}


def write_manifest(
    manifest: dict[str, object],
    artifact_root: Path,
) -> Path:
    """Write one deterministic manifest to the approved local artifact path."""
    path = artifact_manifest_path(artifact_root)
    ensure_approved_manifest_path(path, artifact_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    serialized = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    path.write_text(f"{serialized}\n", encoding="utf-8")
    return path
