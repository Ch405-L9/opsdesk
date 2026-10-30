"""User-local paths for configuration and the workbench database."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_path, user_data_path

APP_NAME = "OpsDesk"


@dataclass(frozen=True)
class AppPaths:
    config_dir: Path
    data_dir: Path

    @property
    def profile_file(self) -> Path:
        return self.config_dir / "profile.yaml"

    @property
    def secrets_file(self) -> Path:
        return self.config_dir / "secrets.yaml"

    @property
    def database_file(self) -> Path:
        return self.data_dir / "workbench.sqlite3"


def app_paths() -> AppPaths:
    """Resolve platform-standard paths, with explicit test/operator overrides."""
    config = os.environ.get("OPSDESK_CONFIG_DIR")
    data = os.environ.get("OPSDESK_DATA_DIR")
    return AppPaths(
        config_dir=Path(config).expanduser() if config else Path(user_config_path(APP_NAME)),
        data_dir=Path(data).expanduser() if data else Path(user_data_path(APP_NAME)),
    )


def ensure_directories(paths: AppPaths | None = None) -> AppPaths:
    resolved = paths or app_paths()
    resolved.config_dir.mkdir(parents=True, exist_ok=True)
    resolved.data_dir.mkdir(parents=True, exist_ok=True)
    return resolved
