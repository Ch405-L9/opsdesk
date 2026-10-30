"""The shared workbench: tool-owned item tables plus user-owned workflow rows.

Rule: importers call `upsert_item`, which never touches `workflow`, `followup` or `note`
beyond creating a default workflow row the first time an item appears.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opsdesk import timeutil
from opsdesk.db import connect, migrate
from opsdesk.paths import AppPaths

AREAS: dict[str, str] = {"lead": "lead", "bid": "bid", "job": "job"}
DEFAULT_STATUS: dict[str, str] = {"lead": "new", "bid": "watch", "job": "saved"}


def area_of(wb_key: str) -> str:
    prefix = wb_key.split(":", 1)[0]
    if prefix not in AREAS:
        raise ValueError(f"Not a workbench key: {wb_key!r}")
    return prefix


def content_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


@contextmanager
def workbench(paths: AppPaths) -> Iterator[sqlite3.Connection]:
    migrate(paths.database_file)
    conn = connect(paths.database_file)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_source(conn: sqlite3.Connection, tool: str, kind: str, ref: str, terms_note: str = "") -> int:
    cur = conn.execute(
        "INSERT INTO source(tool,kind,ref,fetched_at,terms_note) VALUES(?,?,?,?,?)",
        (tool, kind, ref, timeutil.now_iso(), terms_note),
    )
    return int(cur.lastrowid or 0)


def log(conn: sqlite3.Connection, action: str, wb_key: str | None = None,
        detail: dict[str, Any] | None = None, actor: str = "user") -> None:
    conn.execute(
        "INSERT INTO activity(action,wb_key,detail_json,created_at,actor) VALUES(?,?,?,?,?)",
        (action, wb_key, json.dumps(detail or {}, sort_keys=True, default=str), timeutil.now_iso(), actor),
    )


def upsert_item(conn: sqlite3.Connection, wb_key: str, payload: dict[str, Any],
                source_id: int | None = None) -> str:
    """Insert or update one tool-owned item. Returns inserted / updated / unchanged."""
    table = AREAS[area_of(wb_key)]
    digest = content_hash(payload)
    stamp = timeutil.now_iso()
    row = conn.execute(f"SELECT content_hash FROM {table} WHERE wb_key=?", (wb_key,)).fetchone()
    encoded = json.dumps(payload, sort_keys=True, default=str)
    if row is None:
        conn.execute(
            f"INSERT INTO {table}(wb_key,payload_json,content_hash,source_id,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?)",
            (wb_key, encoded, digest, source_id, stamp, stamp),
        )
        result = "inserted"
    elif row["content_hash"] == digest:
        return "unchanged"
    else:
        conn.execute(
            f"UPDATE {table} SET payload_json=?,content_hash=?,source_id=COALESCE(?,source_id),updated_at=? "
            "WHERE wb_key=?",
            (encoded, digest, source_id, stamp, wb_key),
        )
        result = "updated"
    conn.execute(
        "INSERT OR IGNORE INTO workflow(wb_key,status,updated_at,updated_by) VALUES(?,?,?,?)",
        (wb_key, DEFAULT_STATUS[area_of(wb_key)], stamp, "system"),
    )
    return result


def _row_to_item(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(json.loads(row["payload_json"]))
    item.update(
        wb_key=row["wb_key"], status=row["status"], priority=row["priority"], done=bool(row["done"]),
        contacted=bool(row["contacted"]), followup_date=row["followup_date"],
        followup_note=row["followup_note"], notes=row["notes"], updated_at=row["updated_at"],
    )
    return item


def list_items(conn: sqlite3.Connection, area: str, *, status: str | None = None,
               include_closed: bool = True, limit: int = 500) -> list[dict[str, Any]]:
    from opsdesk.workflow import CLOSED

    table = AREAS[area]
    rows = conn.execute(
        f"SELECT t.wb_key, t.payload_json, w.status, w.priority, w.done, w.contacted, w.followup_date, "
        f"w.followup_note, w.notes, w.updated_at FROM {table} t JOIN workflow w ON w.wb_key=t.wb_key "
        "ORDER BY t.updated_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    items = [_row_to_item(r) for r in rows]
    if status:
        items = [i for i in items if i["status"] == status]
    if not include_closed:
        items = [i for i in items if i["status"] not in CLOSED]
    return items


def get_item(conn: sqlite3.Connection, wb_key: str) -> dict[str, Any] | None:
    table = AREAS[area_of(wb_key)]
    row = conn.execute(
        f"SELECT t.wb_key, t.payload_json, w.status, w.priority, w.done, w.contacted, w.followup_date, "
        f"w.followup_note, w.notes, w.updated_at FROM {table} t JOIN workflow w ON w.wb_key=t.wb_key "
        "WHERE t.wb_key=?",
        (wb_key,),
    ).fetchone()
    return _row_to_item(row) if row else None


def resolve_key(conn: sqlite3.Connection, ref: str) -> str:
    """Accept a full wb_key, or a unique case-insensitive name fragment across all areas."""
    if ":" in ref and ref.split(":", 1)[0] in AREAS:
        if get_item(conn, ref) is None:
            raise KeyError(f"No item {ref!r}")
        return ref
    needle = ref.strip().lower()
    hits: list[str] = []
    for area in AREAS:
        for item in list_items(conn, area):
            label = str(item.get("name") or item.get("title") or item.get("recipient") or "").lower()
            if needle and needle in label:
                hits.append(item["wb_key"])
    if not hits:
        raise KeyError(f"No item matches {ref!r}. Use `opsdesk <area> list` to see keys.")
    if len(hits) > 1:
        raise KeyError(f"{len(hits)} items match {ref!r}: {', '.join(hits[:5])}. Use the full key.")
    return hits[0]


def label(item: dict[str, Any]) -> str:
    if item["wb_key"].startswith("job:"):
        return f"{item.get('title', '?')} — {item.get('company', '?')}"
    if item["wb_key"].startswith("bid:"):
        return f"{item.get('sub_agency') or item.get('agency', '?')} — {item.get('recipient', '?')}"
    return str(item.get("name", item["wb_key"]))
