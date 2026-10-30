"""Fail-closed configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import AnyHttpUrl, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from vetted.exceptions import ConfigurationError

DEFAULT_OLLAMA_HOST = AnyHttpUrl("http://127.0.0.1:11434")


class Settings(BaseSettings):
    """Runtime settings with strict no-submit validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["dev", "stage", "production"] = "dev"

    ollama_host: AnyHttpUrl = DEFAULT_OLLAMA_HOST
    generation_model: str = "qwen3:8b"
    review_model: str = "qwen3:14b"
    enable_review_model: bool = False
    embedding_model: str = "nomic-embed-text:latest"
    rag_top_k: int = Field(default=5, ge=1, le=20)


    artifact_root: Path = Path("artifacts")
    chroma_path: Path = Path(".local/chroma")
    candidate_data_path: Path = Path("data/candidate")
    source_resume_path: Path | None = None
    job_data_path: Path = Path("data/jobs")

    allow_fill: bool = False
    allow_submit: bool | None = None

    request_timeout_seconds: int = Field(default=120, ge=5, le=600)

    loaded_config_path: Path | None = None

    @field_validator("allow_submit")
    @classmethod
    def require_submit_explicitly_false(cls, value: bool | None) -> bool:
        """Reject missing or enabled submission configuration."""
        if value is not False:
            raise ValueError("ALLOW_SUBMIT must be explicitly set to false.")
        return value



def load_environment_overlay(app_env: str) -> tuple[dict[str, object], Path]:
    """Load and validate the YAML configuration overlay for one environment."""
    config_path = Path("config") / f"{app_env}.yaml"

    if not config_path.is_file():
        raise ConfigurationError(
            f"Missing environment configuration file: {config_path}"
        )

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigurationError(
            f"Environment configuration must be a YAML mapping: {config_path}"
        )

    return raw, config_path


def get_settings() -> Settings:
    """Load local environment settings and one safe environment YAML overlay."""
    try:
        base = Settings()
        overlay, config_path = load_environment_overlay(base.app_env)

        merged = base.model_dump()
        merged.update(overlay)
        merged["loaded_config_path"] = config_path

        settings = Settings.model_validate(merged)
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid application configuration: {exc}") from exc

    if settings.allow_submit is not False:
        raise ConfigurationError("Submission capability is permanently disabled.")

    return settings
