"""SQLite connection management and deterministic SQL migrations."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 15000")
    return connection


@contextmanager
def open_database(path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def migrate(path: Path, migration_dir: Path | None = None) -> list[str]:
    """Apply each unapplied packaged SQL migration once, in lexical order."""
    directory = migration_dir or Path(str(files("opsdesk").joinpath("migrations")))
    with open_database(path) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
        newly_applied: list[str] = []
        for migration in sorted(directory.glob("*.sql")):
            if migration.name in applied:
                continue
            sql = migration.read_text(encoding="utf-8")
            escaped_name = migration.name.replace("'", "''")
            connection.executescript(
                "BEGIN IMMEDIATE;\n"
                + sql
                + f"\nINSERT INTO schema_migrations(version) VALUES ('{escaped_name}');\nCOMMIT;"
            )
            newly_applied.append(migration.name)
    return newly_applied
