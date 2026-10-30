"""Deterministic, local-only chunking for approved evidence records."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from vetted.schemas.candidate import EvidenceRecord

CHUNKING_ALGORITHM = "paragraph-char-v1"
MAX_CHARS = 1_200
OVERLAP_CHARS = 0


@dataclass(frozen=True)
class RetrievalChunk:
    """One deterministic, source-traceable retrieval chunk."""

    chunk_id: str
    evidence_id: str
    source_filename: str
    chunk_index: int
    text: str
    sha256: str
    char_count: int


def normalize_text(value: str) -> str:
    """Normalize line endings and trim only outer whitespace."""
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def project_evidence_text(record: EvidenceRecord) -> str:
    """Create canonical retrieval text from approved evidence fields only."""
    tags = ", ".join(record.tags)
    pages = ", ".join(str(page) for page in record.source_pages)

    return normalize_text(
        "\n".join(
            (
                f"Evidence ID: {record.evidence_id}",
                f"Category: {record.category}",
                f"Statement: {record.factual_statement}",
                f"Tags: {tags}",
                f"Source document: {record.source_document}",
                f"Source pages: {pages}",
                f"Source excerpt: {record.source_excerpt}",
            )
        )
    )


def split_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """Split normalized text by paragraphs, then fixed character boundaries."""
    if max_chars < 1:
        raise ValueError("max_chars must be at least 1.")

    normalized = normalize_text(text)
    if not normalized:
        return []

    chunks: list[str] = []
    current = ""

    for paragraph in normalized.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""

            for start in range(0, len(paragraph), max_chars):
                piece = paragraph[start : start + max_chars].strip()
                if piece:
                    chunks.append(piece)
            continue

        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)

    return chunks


def chunk_evidence_record(
    record: EvidenceRecord, source_path: Path
) -> list[RetrievalChunk]:
    """Chunk one approved record while preserving source lineage."""
    if not record.approved_for_external_use:
        raise ValueError(
            f"Evidence record is not approved for retrieval: {record.evidence_id}"
        )

    source_filename = source_path.name
    text = project_evidence_text(record)
    chunks: list[RetrievalChunk] = []

    for chunk_index, chunk_text in enumerate(split_text(text)):
        content_hash = sha256(chunk_text.encode("utf-8")).hexdigest()
        chunks.append(
            RetrievalChunk(
                chunk_id=(
                    f"{record.evidence_id}--{chunk_index:03d}--{content_hash[:12]}"
                ),
                evidence_id=record.evidence_id,
                source_filename=source_filename,
                chunk_index=chunk_index,
                text=chunk_text,
                sha256=content_hash,
                char_count=len(chunk_text),
            )
        )

    if not chunks:
        raise ValueError(f"Evidence record produced no chunks: {record.evidence_id}")

    return chunks
