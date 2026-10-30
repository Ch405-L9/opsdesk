"""API keys: environment variables first, then a private secrets.yaml (mode 600) in the config dir."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from opsdesk.paths import AppPaths

KEYS: dict[str, str] = {
    "google_places": "GOOGLE_PLACES_API_KEY",
    "pagespeed": "PAGESPEED_API_KEY",
}


def _read(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(k): str(v) for k, v in raw.items() if v} if isinstance(raw, dict) else {}


def load_secret(paths: AppPaths, name: str) -> str | None:
    env = KEYS.get(name)
    if env and os.environ.get(env):
        return os.environ[env]
    return _read(paths.secrets_file).get(name) or None


def save_secret(paths: AppPaths, name: str, value: str) -> None:
    if name not in KEYS:
        raise ValueError(f"Unknown key {name!r}. Known: {', '.join(KEYS)}")
    data = _read(paths.secrets_file)
    if value:
        data[name] = value.strip()
    else:
        data.pop(name, None)
    paths.secrets_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.secrets_file.with_suffix(".tmp")
    tmp.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(paths.secrets_file)
    os.chmod(paths.secrets_file, 0o600)


def configured(paths: AppPaths) -> dict[str, bool]:
    return {name: bool(load_secret(paths, name)) for name in KEYS}
