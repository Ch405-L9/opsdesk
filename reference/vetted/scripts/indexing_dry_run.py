#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

EXPECTED_MANIFEST_SHA256 = (
    "f0cdd193587668abf4fa92d6347162876b971425b8d3b67ce6554134e15b57b2"
)

REPORT_SCHEMA_VERSION = 1


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def stable_values(items: list[Any]) -> list[Any]:
    return sorted(items, key=lambda item: canonical_json_bytes(item))


def resolve_local_path(raw_path: str, base_dir: Path) -> Path:
    candidate = Path(raw_path)
    return candidate.resolve() if candidate.is_absolute() else (base_dir / candidate).resolve()


def safe_read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return None, f"Manifest does not exist: {path}"
    except UnicodeDecodeError as exc:
        return None, f"Manifest is not valid UTF-8: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"Manifest is not valid JSON: {exc}"

    if not isinstance(payload, dict):
        return None, "Manifest root must be a JSON object."

    return payload, None


def list_records(manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    for key in ("chunks", "records", "documents", "items"):
        candidate = manifest.get(key)
        if candidate is not None:
            if not isinstance(candidate, list):
                return [], f"Manifest field '{key}' must be a JSON array."
            records = [
                item if isinstance(item, dict) else {"__invalid_record__": item}
                for item in candidate
            ]
            return records, None

    return [], (
        "No supported record collection found. Expected one of: "
        "'chunks', 'records', 'documents', or 'items'."
    )


def first_string(record: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def extract_text(record: dict[str, Any]) -> str | None:
    return first_string(record, ("text", "content", "chunk_text", "page_content", "body"))


def extract_id(record: dict[str, Any]) -> str | None:
    return first_string(record, ("chunk_id", "id", "document_id", "record_id"))


def extract_source_path(record: dict[str, Any]) -> str | None:
    direct = first_string(record, ("source_filename", "source_path", "file_path", "path", "source_file"))
    if direct:
        return direct

    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        return first_string(metadata, ("source_filename", "source_path", "file_path", "path", "source_file"))

    return None


def validate_records(
    records: list[dict[str, Any]],
    source_root: Path,
) -> dict[str, Any]:
    ids: list[str] = []
    missing_source_files: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    empty_chunks: list[dict[str, Any]] = []
    source_paths_seen: set[str] = set()
    total_characters = 0
    largest_chunk_characters = 0

    for index, record in enumerate(records):
        if "__invalid_record__" in record:
            invalid_records.append({
                "record_index": index,
                "reason": "Record must be a JSON object.",
            })
            continue

        record_id = extract_id(record)
        text = extract_text(record)
        source_path = extract_source_path(record)

        if record_id is None:
            invalid_records.append({
                "record_index": index,
                "reason": "Missing stable record ID.",
            })
        else:
            ids.append(record_id)

        if text is None or not text.strip():
            empty_chunks.append({
                "record_index": index,
                "record_id": record_id,
            })
        else:
            char_count = len(text)
            total_characters += char_count
            largest_chunk_characters = max(largest_chunk_characters, char_count)

        if source_path is None:
            invalid_records.append({
                "record_index": index,
                "record_id": record_id,
                "reason": "Missing local source path.",
            })
        else:
            resolved = resolve_local_path(source_path, source_root)
            source_paths_seen.add(str(resolved))
            if not resolved.is_file():
                missing_source_files.append({
                    "record_index": index,
                    "record_id": record_id,
                    "declared_path": source_path,
                    "resolved_path": str(resolved),
                })

    id_counts = Counter(ids)
    duplicate_chunk_ids = sorted(
        record_id for record_id, count in id_counts.items() if count > 1
    )

    return {
        "records_planned": len(records),
        "unique_record_ids": len(set(ids)),
        "duplicate_record_ids": duplicate_chunk_ids,
        "missing_source_files": stable_values(missing_source_files),
        "invalid_records": stable_values(invalid_records),
        "empty_chunks": stable_values(empty_chunks),
        "source_files_referenced": len(source_paths_seen),
        "total_text_characters": total_characters,
        "largest_chunk_characters": largest_chunk_characters,
    }


def build_report(
    manifest_path: Path,
    manifest_digest: str,
    expected_digest: str | None,
    manifest: dict[str, Any] | None,
    manifest_error: str | None,
    source_root: Path,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "mode": "indexing_dry_run",
        "network_access": False,
        "embedding_runtime_loaded": False,
        "vector_store_created": False,
        "persistent_storage_created": False,
        "manifest_path": str(manifest_path.resolve()),
        "source_root": str(source_root.resolve()),
        "manifest_file_sha256": manifest_digest,
        "expected_manifest_file_sha256": expected_digest,
        "manifest_matches_expected": (
            None if expected_digest is None else manifest_digest == expected_digest
        ),
        "manifest_parse_error": manifest_error,
    }

    if manifest is None:
        report.update({
            "record_collection_key": None,
            "schema_validation": "fail",
            "records_planned": 0,
            "unique_record_ids": 0,
            "duplicate_record_ids": [],
            "missing_source_files": [],
            "invalid_records": [],
            "empty_chunks": [],
            "source_files_referenced": 0,
            "total_text_characters": 0,
            "largest_chunk_characters": 0,
            "overall_status": "fail",
        })
        return report

    records, record_error = list_records(manifest)
    if record_error:
        report.update({
            "record_collection_key": None,
            "schema_validation": "fail",
            "records_planned": 0,
            "unique_record_ids": 0,
            "duplicate_record_ids": [],
            "missing_source_files": [],
            "invalid_records": [{"reason": record_error}],
            "empty_chunks": [],
            "source_files_referenced": 0,
            "total_text_characters": 0,
            "largest_chunk_characters": 0,
            "overall_status": "fail",
        })
        return report

    record_collection_key = next(
        key for key in ("chunks", "records", "documents", "items")
        if key in manifest
    )

    validation = validate_records(records, source_root)
    failed_checks = [
        manifest_error is not None,
        expected_digest is not None and manifest_digest != expected_digest,
        bool(validation["duplicate_record_ids"]),
        bool(validation["missing_source_files"]),
        bool(validation["invalid_records"]),
        bool(validation["empty_chunks"]),
    ]

    report.update({
        "record_collection_key": record_collection_key,
        "schema_validation": "pass" if not validation["invalid_records"] else "fail",
        **validation,
        "overall_status": "fail" if any(failed_checks) else "pass",
    })
    return report


def write_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report_without_digest = dict(report)
    report_without_digest.pop("canonical_report_sha256", None)

    canonical_digest = sha256_bytes(canonical_json_bytes(report_without_digest))
    report_with_digest = {
        **report_without_digest,
        "canonical_report_sha256": canonical_digest,
    }

    serialized = json.dumps(
        report_with_digest,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"

    output_path.write_text(serialized, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a planned retrieval index without embeddings, storage, or network access."
    )
    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help="Path to the local evidence manifest JSON.",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("."),
        help="Root directory used to resolve relative source paths.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/indexing_dry_run_report.json"),
        help="Output path for the deterministic dry-run report.",
    )
    parser.add_argument(
        "--expected-manifest-sha256",
        default=EXPECTED_MANIFEST_SHA256,
        help="Expected literal SHA-256 of the manifest; use an empty string to disable.",
    )
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    source_root = args.source_root.resolve()
    expected_digest = args.expected_manifest_sha256.strip() or None

    if manifest_path.is_file():
        manifest_digest = sha256_file(manifest_path)
    else:
        manifest_digest = ""

    manifest, manifest_error = safe_read_json(manifest_path)

    report = build_report(
        manifest_path=manifest_path,
        manifest_digest=manifest_digest,
        expected_digest=expected_digest,
        manifest=manifest,
        manifest_error=manifest_error,
        source_root=source_root,
    )
    write_report(report, args.output)

    print(
        json.dumps(
            {
                "overall_status": report["overall_status"],
                "manifest_file_sha256": report["manifest_file_sha256"],
                "manifest_matches_expected": report["manifest_matches_expected"],
                "records_planned": report["records_planned"],
                "report_path": str(args.output),
            },
            sort_keys=True,
        )
    )

    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
