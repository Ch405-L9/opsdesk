"""No module reads outside this repository.

Phase 1A reads only `config/*.yaml`. There is no external-directory inspection, no résumé
parsing, no legal-record read, and no project-folder scan.
"""

import ast
import re
from pathlib import Path

ABSOLUTE_PATH = re.compile(r"""['"](/(?!/)[A-Za-z0-9._~\-]+(?:/[A-Za-z0-9._~\-]+)+)['"]""")
HOME_PATH = re.compile(r"""['"]~[/A-Za-z]""")

BANNED_CALLS = {"expanduser", "gethostname", "getlogin", "system", "popen", "run", "Popen"}
BANNED_MODULES = {"subprocess", "shutil", "glob", "os"}


def test_no_absolute_path_literals(src_dir: Path) -> None:
    for path in sorted(src_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert not ABSOLUTE_PATH.search(text), f"{path} contains an absolute path literal"
        assert not HOME_PATH.search(text), f"{path} contains a home-directory path literal"


def test_no_process_or_filesystem_traversal_modules(src_dir: Path) -> None:
    for path in sorted(src_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots = {node.module.split(".")[0]}
            else:
                continue
            offending = roots & BANNED_MODULES
            assert not offending, f"{path} imports {sorted(offending)}"


def test_no_environment_reads(src_dir: Path) -> None:
    """Phase 1A reads no environment variable, so no secret can reach the process."""
    for path in sorted(src_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in ("os.environ", "getenv", "dotenv"):
            assert token not in text, f"{path} reads the environment ({token})"


def test_no_banned_call_names(src_dir: Path) -> None:
    for path in sorted(src_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                assert name not in BANNED_CALLS, f"{path} calls {name}()"


def test_config_is_the_only_file_read(src_dir: Path) -> None:
    """Exactly one module opens a file, and only inside `config/`."""
    openers = [
        path
        for path in sorted(src_dir.rglob("*.py"))
        if ".open(" in path.read_text(encoding="utf-8")
    ]
    assert [path.name for path in openers] == ["loader.py"]
