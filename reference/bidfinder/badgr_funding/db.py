"""SQLite storage: connection, migrations and opportunity CRUD with change history."""
import sqlite3
from pathlib import Path

from badgr_funding import dates

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
DEFAULT_DB = Path("data/funding.sqlite")

# Columns the CLI/importer may set directly (id/dedupe_key/timestamps are managed).
EDITABLE = (
    "sponsor", "program", "cycle", "funding_type", "official_url", "geography",
    "for_profit_eligible", "ownership_requirements", "revenue_history_rules",
    "min_months_in_business", "registrations_required", "prerequisite_tier",
    "amount_min_cents", "amount_max_cents", "deadline_date", "deadline_time", "deadline_tz",
    "rolling", "match_required", "reimbursement_basis", "uses_allowed", "uses_disallowed",
    "fees", "rate_apr", "term_months", "guarantee", "collateral", "repayment_gate",
    "required_documents", "contact", "source_status", "source_checked_at", "source_checked_tz",
    "eligibility", "application_status", "effort_hours", "revisit_date", "next_action", "owner",
    "followup_date", "override_score", "override_reason", "caution", "notes",
)


def connect(path=DEFAULT_DB):
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn):
    """Apply pending migrations in filename order. Returns list of applied names."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
    applied = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in done:
            continue
        with conn:
            conn.executescript(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations VALUES (?, ?)", (path.name, dates.now_iso()))
        applied.append(path.name)
    return applied


def dedupe_key(sponsor, program, cycle):
    norm = lambda s: " ".join((s or "").lower().replace("&", "and").split())
    return f"{norm(sponsor)}|{norm(program)}|{norm(cycle)}"


def get(conn, opp_id):
    row = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opp_id,)).fetchone()
    return dict(row) if row else None


def insert(conn, opp_id, fields):
    now = dates.now_iso()
    data = {k: v for k, v in fields.items() if k in EDITABLE}
    data.update(id=opp_id, created_at=now, updated_at=now,
                dedupe_key=dedupe_key(data.get("sponsor"), data.get("program"), data.get("cycle")))
    cols = ", ".join(data)
    marks = ", ".join("?" for _ in data)
    with conn:
        conn.execute(f"INSERT INTO opportunities ({cols}) VALUES ({marks})", tuple(data.values()))
        conn.execute("INSERT INTO history (opportunity_id, field, old_value, new_value, changed_at, reason) "
                     "VALUES (?, '*', NULL, 'created', ?, ?)", (opp_id, now, fields.get("_reason")))


def update(conn, opp_id, fields, reason):
    """Update fields; every actual change writes a history row. Never deletes."""
    if not reason or not reason.strip():
        raise ValueError("update requires a reason")
    current = get(conn, opp_id)
    if current is None:
        raise KeyError(opp_id)
    changes = {k: v for k, v in fields.items() if k in EDITABLE and current.get(k) != v}
    if not changes:
        return {}
    now = dates.now_iso()
    merged = {**current, **changes}
    changes["dedupe_key"] = dedupe_key(merged["sponsor"], merged["program"], merged["cycle"])
    sets = ", ".join(f"{k} = ?" for k in changes) + ", updated_at = ?"
    with conn:
        conn.execute(f"UPDATE opportunities SET {sets} WHERE id = ?", (*changes.values(), now, opp_id))
        for k, v in changes.items():
            if k != "dedupe_key":
                conn.execute("INSERT INTO history (opportunity_id, field, old_value, new_value, changed_at, reason) "
                             "VALUES (?, ?, ?, ?, ?, ?)",
                             (opp_id, k, _txt(current.get(k)), _txt(v), now, reason))
    changes.pop("dedupe_key")
    return changes


def add_source(conn, opp_id, url, kind, method, excerpt=None, checked_at=None, tz=dates.LOCAL_TZ_NAME):
    with conn:
        conn.execute("INSERT OR IGNORE INTO sources (opportunity_id, url, kind, excerpt, method, checked_at, checked_tz) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (opp_id, url, kind, excerpt, method, checked_at or dates.now_iso(), tz))


def set_criterion(conn, opp_id, criterion, status, material=True, evidence=None, private_key=None, pass_when=None):
    if private_key:
        status, evidence = "unknown", "owner-screened (private)"
    with conn:
        conn.execute("INSERT INTO criteria (opportunity_id, criterion, status, material, evidence, private_key, pass_when) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?) "
                     "ON CONFLICT(opportunity_id, criterion) DO UPDATE SET status = excluded.status, "
                     "material = excluded.material, evidence = excluded.evidence, "
                     "private_key = excluded.private_key, pass_when = excluded.pass_when",
                     (opp_id, criterion, status, int(bool(material)), evidence, private_key, pass_when))


def criteria(conn, opp_id):
    return [dict(r) for r in conn.execute("SELECT * FROM criteria WHERE opportunity_id = ? ORDER BY criterion", (opp_id,))]


def sources(conn, opp_id):
    return [dict(r) for r in conn.execute("SELECT * FROM sources WHERE opportunity_id = ? ORDER BY checked_at", (opp_id,))]


def history(conn, opp_id):
    return [dict(r) for r in conn.execute("SELECT * FROM history WHERE opportunity_id = ? ORDER BY id", (opp_id,))]


def all_opportunities(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM opportunities ORDER BY id")]


def _txt(v):
    return None if v is None else str(v)
