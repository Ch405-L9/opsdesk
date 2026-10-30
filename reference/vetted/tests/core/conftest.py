"""Test configuration.

Puts `src/` and `tests/` on the import path so the suite runs from a source checkout without
installing the package. No test performs network access, writes outside the repository, or
reads any path outside it.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
CORE_DIR = SRC_DIR / "vetted" / "core"
TESTS_DIR = REPO_ROOT / "tests" / "core"

for _path in (SRC_DIR, TESTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """The repository root."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def config_dir() -> Path:
    """The repository's shipped `config/` directory."""
    return REPO_ROOT / "config" / "policy"


@pytest.fixture(scope="session")
def src_dir() -> Path:
    """The `src/` directory."""
    return CORE_DIR


@pytest.fixture(autouse=True)
def synthetic_dossier_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the dossier loader at an invented dossier, so no test needs real candidate data."""
    import yaml

    from fixtures.dossier_synthetic import synthetic_dossier
    from vetted.core.dossier import loader

    path = tmp_path / "dossier.yaml"
    path.write_text(
        yaml.safe_dump(synthetic_dossier().model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(loader, "DEFAULT_DOSSIER_PATH", path)
    return path
