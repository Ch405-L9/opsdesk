"""SQLite store: a search cache and an accumulating lead table.

Why this exists, in one number: Places Text Search bills at the ENTERPRISE SKU
($35/1,000, only 1,000 free calls/month) because the field mask requests
websiteUri, nationalPhoneNumber, rating and userRatingCount. Every repeated
search without a cache is a billable call for data already on disk.

With the cache, the same query inside the TTL costs nothing. That is the whole
difference between "safe at any usage" and "a surprise invoice".

Also: one request returns up to 20 results for the same price as one result, so
always ask for 20. Cost is per REQUEST, not per business returned.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlparse
from typing import List, Optional

DEFAULT_DB = Path.home() / ".local/share/badgr/icp.db"
CACHE_TTL_SECONDS = 14 * 24 * 3600   # business listings change slowly

SCHEMA = """
CREATE TABLE IF NOT EXISTS search_cache (
    query_key   TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    fetched_at  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS leads (
    domain_or_name TEXT PRIMARY KEY,
    name        TEXT, website TEXT, phone TEXT, address TEXT,
    rating      REAL, review_count INTEGER,
    vertical    TEXT, location TEXT,
    has_website INTEGER,
    need        INTEGER, ability INTEGER, fit INTEGER, reach INTEGER,
    priority    INTEGER, disqualified TEXT,
    first_seen  INTEGER, last_seen INTEGER
);
CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority DESC);
CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_or_name TEXT NOT NULL,
    event       TEXT NOT NULL,      -- contacted | replied | meeting | proposal | won | lost
    detail      TEXT,
    loss_reason TEXT,
    at          INTEGER NOT NULL
);
"""

def lead_key(row: dict) -> Optional[str]:
    """Stable identity for a business: the registrable host, else the name.

    The old key was the full URL. Google rewrites utm_* parameters on the
    websiteUri it returns, so the same practice reappeared as a new row on
    every refresh - duplicate leads, duplicate outreach, and orphaned outcome
    rows that silently broke the retraining counter.
    """
    site = (row.get("website") or "").strip().lower()
    if site:
        host = urlparse(site if "//" in site else "//" + site).netloc.lower()
        host = host.split(":")[0].removeprefix("www.")
        if host and "." in host:
            return host
    name = (row.get("name") or "").strip().lower()
    return name or None


class Store:
    def __init__(self, path=DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---- search cache -------------------------------------------------------
    @staticmethod
    def _key(industry: str, location: str) -> str:
        return f"{(industry or '').strip().lower()}|{(location or '').strip().lower()}"

    def cached_search(self, industry: str, location: str,
                      ttl: int = CACHE_TTL_SECONDS) -> Optional[List[dict]]:
        row = self.conn.execute(
            "SELECT payload, fetched_at FROM search_cache WHERE query_key=?",
            (self._key(industry, location),)).fetchone()
        if not row:
            return None
        if time.time() - row["fetched_at"] > ttl:
            return None            # stale: let the caller pay for a fresh one
        return json.loads(row["payload"])

    def put_search(self, industry: str, location: str, rows: List[dict]) -> None:
        # Never cache an empty result for 14 days. One transient zero-result
        # response would then answer every retry for two weeks, and read as
        # "no such businesses exist" - indistinguishable from the truth.
        if not rows:
            return
        self.conn.execute(
            "INSERT OR REPLACE INTO search_cache(query_key,payload,fetched_at) VALUES(?,?,?)",
            (self._key(industry, location), json.dumps(rows), int(time.time())))
        self.conn.commit()

    def cache_age_days(self, industry: str, location: str) -> Optional[float]:
        row = self.conn.execute("SELECT fetched_at FROM search_cache WHERE query_key=?",
                                (self._key(industry, location),)).fetchone()
        return None if not row else (time.time() - row["fetched_at"]) / 86400

    # ---- leads --------------------------------------------------------------
    def upsert_leads(self, rows: List[dict], vertical: str = "", location: str = "") -> int:
        now = int(time.time())
        n = 0
        for r in rows:
            key = lead_key(r)
            if not key:
                continue

            # A business that gains a website changes identity from its name to
            # its host. Collapse the old name-keyed row into the new one instead
            # of leaving a duplicate behind - that duplicate is exactly the
            # "you have no website" row that generates a wrong cold email.
            name_key = (r.get("name") or "").strip().lower()
            if name_key and name_key != key:
                self.conn.execute(
                    "UPDATE outcomes SET domain_or_name=? WHERE domain_or_name=?",
                    (key, name_key))
                self.conn.execute("DELETE FROM leads WHERE domain_or_name=?", (name_key,))
            self.conn.execute("""
                INSERT INTO leads(domain_or_name,name,website,phone,address,rating,review_count,
                                  vertical,location,has_website,need,ability,fit,reach,priority,
                                  disqualified,first_seen,last_seen)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(domain_or_name) DO UPDATE SET
                  name=excluded.name, website=excluded.website, phone=excluded.phone,
                  -- has_website was previously NOT updated, so a row could hold a
                  -- real URL with has_website=0, which skipped the audit and
                  -- generated "you have no website" emails to sites we had.
                  has_website=excluded.has_website, address=excluded.address,
                  vertical=COALESCE(excluded.vertical, vertical),
                  location=COALESCE(excluded.location, location),
                  rating=excluded.rating, review_count=excluded.review_count,
                  need=excluded.need, ability=excluded.ability, fit=excluded.fit,
                  reach=excluded.reach, priority=excluded.priority,
                  disqualified=excluded.disqualified, last_seen=excluded.last_seen
            """, (key, r.get("name"), r.get("website"), r.get("phone"), r.get("address"),
                  r.get("rating"), r.get("review_count"), vertical or r.get("vertical"), location,
                  1 if r.get("has_website") else 0, r.get("need"), r.get("ability"), r.get("fit"),
                  r.get("reach"), r.get("priority"), r.get("disqualified"), now, now))
            n += 1
        self.conn.commit()
        return n

    def top_leads(self, limit: int = 20, vertical: str = "") -> List[sqlite3.Row]:
        sql = "SELECT * FROM leads WHERE disqualified IS NULL"
        args: list = []
        if vertical:
            sql += " AND vertical=?"; args.append(vertical)
        sql += " ORDER BY priority DESC LIMIT ?"; args.append(limit)
        return self.conn.execute(sql, args).fetchall()

    def count_leads(self) -> int:
        return self.conn.execute("SELECT COUNT(*) c FROM leads").fetchone()["c"]

    # ---- outcomes (what makes the scorer trainable later) -------------------
    def log_outcome(self, key: str, event: str, detail: str = "", loss_reason: str = "") -> None:
        self.conn.execute(
            "INSERT INTO outcomes(domain_or_name,event,detail,loss_reason,at) VALUES(?,?,?,?,?)",
            (key.strip().lower(), event, detail, loss_reason, int(time.time())))
        self.conn.commit()

    def outcome_counts(self) -> dict:
        rows = self.conn.execute("SELECT event, COUNT(*) c FROM outcomes GROUP BY event").fetchall()
        return {r["event"]: r["c"] for r in rows}
