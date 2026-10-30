"""User-owned workflow: status, priority, done, contacted, follow-ups and notes."""

from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Any

from opsdesk import timeutil
from opsdesk.workbench import area_of, list_items, log

STATUSES: dict[str, list[str]] = {
    "lead": ["new", "researching", "contacted", "replied", "meeting", "proposal", "won", "lost", "skip"],
    "bid": ["watch", "researching", "not_eligible", "pursue", "drafting", "submitted_manually", "won", "lost", "closed"],
    "job": ["saved", "assessed", "drafting", "applied_manually", "interview", "offer", "rejected", "pass"],
}
PRIORITIES = ["high", "normal", "low"]
CLOSED = {"won", "lost", "skip", "closed", "not_eligible", "rejected", "pass"}
USER_FIELDS = {"status", "priority", "done", "contacted", "followup_date", "followup_note", "notes"}


class WorkflowError(ValueError):
    pass


def _clean(area: str, field: str, value: Any) -> Any:
    if field == "status":
        v = str(value).strip().lower().replace(" ", "_")
        if v not in STATUSES[area]:
            raise WorkflowError(f"Status {value!r} is not valid for {area}s. Choose: {', '.join(STATUSES[area])}")
        return v
    if field == "priority":
        v = str(value).strip().lower()
        if v not in PRIORITIES:
            raise WorkflowError(f"Priority must be one of {', '.join(PRIORITIES)}")
        return v
    if field in {"done", "contacted"}:
        if isinstance(value, str):
            return 1 if value.strip().lower() in {"1", "true", "yes", "y", "x", "☑", "✓", "✔"} else 0
        return 1 if value else 0
    if field == "followup_date":
        if value in (None, ""):
            return None
        parsed = timeutil.parse_date(value)
        if parsed is None:
            raise WorkflowError(f"Follow-up date {value!r} is not a date (YYYY-MM-DD)")
        return parsed.isoformat()
    return "" if value is None else str(value)


def set_fields(conn: sqlite3.Connection, wb_key: str, actor: str = "user", **changes: Any) -> dict[str, Any]:
    unknown = set(changes) - USER_FIELDS
    if unknown:
        raise WorkflowError(f"Not a workflow field: {', '.join(sorted(unknown))}")
    area = area_of(wb_key)
    if conn.execute("SELECT 1 FROM workflow WHERE wb_key=?", (wb_key,)).fetchone() is None:
        raise KeyError(f"No item {wb_key!r}")
    cleaned = {k: _clean(area, k, v) for k, v in changes.items()}
    if not cleaned:
        return cleaned
    stamp = timeutil.now_iso()
    sets = ", ".join(f"{k}=?" for k in cleaned)
    conn.execute(
        f"UPDATE workflow SET {sets}, updated_at=?, updated_by=? WHERE wb_key=?",
        (*cleaned.values(), stamp, actor, wb_key),
    )
    log(conn, "workflow.set", wb_key, cleaned, actor)
    return cleaned


def follow(conn: sqlite3.Connection, wb_key: str, when: dt.date, note: str = "", actor: str = "user") -> None:
    set_fields(conn, wb_key, actor, followup_date=when.isoformat(), followup_note=note, done=0)
    conn.execute(
        "INSERT INTO followup(wb_key,due_at,note,created_at) VALUES(?,?,?,?)",
        (wb_key, when.isoformat(), note, timeutil.now_iso()),
    )


def add_note(conn: sqlite3.Connection, wb_key: str, body: str, actor: str = "user", tz: str | None = None) -> None:
    body = body.strip()
    if not body:
        raise WorkflowError("Note is empty")
    row = conn.execute("SELECT notes FROM workflow WHERE wb_key=?", (wb_key,)).fetchone()
    if row is None:
        raise KeyError(f"No item {wb_key!r}")
    stamped = f"[{timeutil.today(tz).isoformat()}] {body}"
    combined = f"{row['notes']}\n{stamped}".strip() if row["notes"] else stamped
    conn.execute("INSERT INTO note(wb_key,body,created_at,created_by) VALUES(?,?,?,?)",
                 (wb_key, body, timeutil.now_iso(), actor))
    set_fields(conn, wb_key, actor, notes=combined)


def mark_done(conn: sqlite3.Connection, wb_key: str, actor: str = "user") -> None:
    set_fields(conn, wb_key, actor, done=1)
    conn.execute("UPDATE followup SET completed_at=? WHERE wb_key=? AND completed_at IS NULL",
                 (timeutil.now_iso(), wb_key))


def snooze(conn: sqlite3.Connection, wb_key: str, days: int, tz: str | None = None, actor: str = "user") -> dt.date:
    when = timeutil.today(tz) + dt.timedelta(days=days)
    set_fields(conn, wb_key, actor, followup_date=when.isoformat(), done=0)
    return when


def today_view(conn: sqlite3.Connection, tz: str | None = None, horizon_days: int = 7) -> dict[str, list[dict[str, Any]]]:
    """Open follow-ups bucketed in the user's time zone."""
    base = timeutil.today(tz)
    buckets: dict[str, list[dict[str, Any]]] = {"overdue": [], "today": [], "upcoming": []}
    for area in ("lead", "bid", "job"):
        for item in list_items(conn, area):
            due = timeutil.parse_date(item.get("followup_date"))
            if due is None or item["done"] or item["status"] in CLOSED:
                continue
            if due < base:
                buckets["overdue"].append(item)
            elif due == base:
                buckets["today"].append(item)
            elif (due - base).days <= horizon_days:
                buckets["upcoming"].append(item)
    for rows in buckets.values():
        rows.sort(key=lambda i: (i["followup_date"], PRIORITIES.index(i["priority"]) if i["priority"] in PRIORITIES else 1))
    return buckets


def counts(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for area in ("lead", "bid", "job"):
        tally: dict[str, int] = {}
        for item in list_items(conn, area):
            tally[item["status"]] = tally.get(item["status"], 0) + 1
        out[area] = tally
    return out
