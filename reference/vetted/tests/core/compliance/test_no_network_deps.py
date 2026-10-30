"""Phase 1A has no external-action surface: no network, no browser, no model provider."""

import ast
from pathlib import Path

BANNED = {
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "urllib3",
    "http",
    "socket",
    "ssl",
    "ftplib",
    "smtplib",
    "telnetlib",
    "webbrowser",
    "selenium",
    "playwright",
    "bs4",
    "scrapy",
    "openai",
    "anthropic",
    "ollama",
    "litellm",
    "langchain",
    "mcp",
    "boto3",
    "chromadb",
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


def test_no_network_or_provider_imports_in_source(src_dir: Path) -> None:
    for path in sorted(src_dir.rglob("*.py")):
        offending = _imported_roots(path) & BANNED
        assert not offending, f"{path} imports banned package(s): {sorted(offending)}"


def test_no_network_or_provider_dependencies_declared(repo_root: Path) -> None:
    text = (repo_root / "pyproject.toml").read_text(encoding="utf-8").lower()
    for name in BANNED - {"http", "socket", "ssl"}:
        assert name not in text, f"pyproject.toml declares a banned dependency: {name}"


def test_source_contains_no_url_literals(src_dir: Path) -> None:
    for path in sorted(src_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for scheme in ("http://", "https://", "ftp://", "ws://"):
            assert scheme not in text, f"{path} contains a URL literal"
