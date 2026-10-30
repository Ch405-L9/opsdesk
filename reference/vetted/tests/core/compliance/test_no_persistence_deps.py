"""Phase 1A declares and imports no persistence layer."""

import ast
from pathlib import Path

BANNED = {
    "sqlite3",
    "sqlalchemy",
    "alembic",
    "psycopg",
    "psycopg2",
    "pymysql",
    "asyncpg",
    "redis",
    "pymongo",
}


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_no_persistence_imports_in_source(src_dir: Path) -> None:
    for path in sorted(src_dir.rglob("*.py")):
        offending = _imported_roots(path) & BANNED
        assert not offending, f"{path} imports persistence package(s): {sorted(offending)}"


def test_no_persistence_dependencies_declared(repo_root: Path) -> None:
    text = (repo_root / "pyproject.toml").read_text(encoding="utf-8").lower()
    for name in BANNED:
        assert name not in text, f"pyproject.toml declares a persistence dependency: {name}"


def test_no_migration_directory(repo_root: Path) -> None:
    assert not (repo_root / "migrations").exists()
    assert not (repo_root / "alembic.ini").exists()
