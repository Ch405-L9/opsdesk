"""Hard lines enforced on the source tree itself."""

import ast
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "opsdesk"
BANNED = {"selenium", "playwright", "browser_use", "pyautogui", "smtplib", "mechanize"}


def test_no_automation_or_sending_imports():
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        roots = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        roots |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module and n.level == 0}
        assert not roots & BANNED, f"{path} imports {roots & BANNED}"


def test_no_scheduler_or_shell_in_source():
    text = "\n".join(p.read_text(encoding="utf-8") for p in SRC.rglob("*.py"))
    assert "crontab" not in text and "shell=True" not in text and "subprocess" not in text


def test_dashboard_binds_loopback_only():
    cli = (SRC / "cli.py").read_text(encoding="utf-8")
    assert 'host="127.0.0.1"' in cli and "0.0.0.0" not in cli


def test_no_personal_data_in_tracked_files():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
    home = re.compile(r"/home/[a-z][\w-]*/|/Users/[A-Z]")
    for name in files:
        if name.startswith(("reference/", "tests/fixtures/")) or not name.endswith((".py", ".md", ".html", ".toml", ".yaml", ".yml", ".css", ".js")):
            continue
        text = (ROOT / name).read_text(encoding="utf-8", errors="ignore")
        for found in email.findall(text):
            assert found.split("@")[1].endswith(("example.com", "example", "example.test", "noreply.github.com")), f"{name}: {found}"
        assert not home.search(text), f"{name} contains a home path"
