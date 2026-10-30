"""Jobs and applications. OpsDesk never submits an application; it records what you did by hand."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from opsdesk import timeutil
from opsdesk.jobs import capture, evidence
from opsdesk.jobs.assess import assess, resume_bullets
from opsdesk.paths import AppPaths
from opsdesk.profile import load_profile
from opsdesk.workbench import add_source, get_item, log, upsert_item, workbench
from opsdesk.workflow import set_fields

NO_SUBMIT = "OpsDesk never submits applications. Apply on the employer's site yourself, then record it here."


def add(paths: AppPaths, text: str, origin: str = "manual capture") -> tuple[str, str]:
    job = capture.parse(text)
    key = capture.job_key(job)
    job["capture_text"] = text
    with workbench(paths) as conn:
        src = add_source(conn, "jobs", "file", origin, "User-provided posting text")
        outcome = upsert_item(conn, key, job, src)
        log(conn, "jobs.add", key, {"outcome": outcome})
    return key, outcome


def run_assessment(paths: AppPaths, wb_key: str) -> dict[str, Any]:
    profile = load_profile(paths.profile_file)
    items = evidence.load(paths)
    with workbench(paths) as conn:
        item = get_item(conn, wb_key)
        if item is None or not wb_key.startswith("job:"):
            raise KeyError(f"No job {wb_key!r}")
        result = assess(item, items, profile)
        payload = {k: v for k, v in item.items() if k not in
                   {"wb_key", "status", "priority", "done", "contacted", "followup_date", "followup_note", "notes", "updated_at"}}
        payload["assessment"] = result
        payload["assessed_at"] = timeutil.now_iso(profile.timezone)
        upsert_item(conn, wb_key, payload)
        if item["status"] == "saved":
            set_fields(conn, wb_key, "system", status="assessed")
        log(conn, "jobs.assess", wb_key, {"technology_alignment": result["technology_alignment"]})
    return result


def draft_resume(paths: AppPaths, wb_key: str) -> list[dict[str, str]]:
    with workbench(paths) as conn:
        item = get_item(conn, wb_key)
    if item is None:
        raise KeyError(f"No job {wb_key!r}")
    return resume_bullets(item, evidence.load(paths))


def record_applied(paths: AppPaths, wb_key: str, note: str = "") -> Path:
    """Application receipt: a dated copy of exactly what was posted, kept privately."""
    profile = load_profile(paths.profile_file)
    with workbench(paths) as conn:
        item = get_item(conn, wb_key)
        if item is None:
            raise KeyError(f"No job {wb_key!r}")
        stamp = timeutil.now_iso(profile.timezone)
        slug = re.sub(r"[^a-z0-9]+", "-", f"{item.get('company', '')}-{item.get('title', '')}".lower()).strip("-")[:60]
        folder = paths.data_dir / "receipts"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{stamp[:10]}_{slug}.md"
        path.write_text(f"# Application receipt\nRecorded: {stamp}\nJob: {item.get('title')} at {item.get('company')}\n"
                        f"URL: {item.get('url') or '-'}\nPosting SHA-256: {item.get('snapshot_sha256')}\nNote: {note}\n\n"
                        f"## Posting as captured\n\n{item.get('capture_text', '')}\n", encoding="utf-8")
        path.chmod(0o600)
        receipt = {"recorded_at": stamp, "path": str(path), "posting_sha256": item.get("snapshot_sha256"), "note": note}
        conn.execute(
            "INSERT INTO application(wb_key,job_key,status,applied_at,receipt_json,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?) ON CONFLICT(wb_key) DO UPDATE SET status=excluded.status, "
            "applied_at=excluded.applied_at, receipt_json=excluded.receipt_json, updated_at=excluded.updated_at",
            ("app:" + wb_key, wb_key, "applied_manually", stamp, json.dumps(receipt), stamp, stamp),
        )
        set_fields(conn, wb_key, "user", status="applied_manually")
        log(conn, "jobs.applied", wb_key, receipt)
    return path
