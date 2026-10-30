"""Configuration loading.

Reads only YAML files inside this repository's `config/` directory. There is no network
access, no environment scanning, and no read outside the repository.
"""

from pathlib import Path
from typing import Any

import yaml

from vetted.core.config.schema import AssessmentConfig

__all__ = [
    "CONFIG_FILENAMES",
    "default_config_dir",
    "load_assessment_config",
    "load_ready_assessment_config",
    "repository_root",
]

CONFIG_FILENAMES: dict[str, str] = {
    "scoring": "scoring.yaml",
    "compensation": "compensation.yaml",
    "blockers": "blockers.yaml",
    "risk_flags": "risk_flags.yaml",
}


def repository_root() -> Path:
    """Return the repository root, resolved relative to this file.

    Phase 1A runs from a source checkout. Packaged-install resolution is deferred.
    """
    return Path(__file__).resolve().parents[4]


def default_config_dir() -> Path:
    """Return the repository's `config/policy/` directory."""
    return repository_root() / "config" / "policy"


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a YAML mapping at the top level")
    return data


def load_assessment_config(config_dir: Path | None = None) -> AssessmentConfig:
    """Parse and structurally validate the configuration.

    Succeeds while policy keys remain UNRESOLVED. Use `load_ready_assessment_config` when an
    assessment is actually going to be executed.
    """
    directory = config_dir if config_dir is not None else default_config_dir()
    sections: dict[str, Any] = {}
    for section, filename in CONFIG_FILENAMES.items():
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"missing configuration file: {path}")
        sections[section] = _read_yaml(path)
    return AssessmentConfig.model_validate(sections)


def load_ready_assessment_config(config_dir: Path | None = None) -> AssessmentConfig:
    """Load the configuration and require every policy decision to be approved.

    Raises `AssessmentPolicyUnresolvedError` while any policy key is UNRESOLVED.
    """
    config = load_assessment_config(config_dir)
    config.require_ready()
    return config
