"""Business profile validation and private local persistence."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SalaryTargets(BaseModel):
    """Optional neutral salary range supplied by the user."""

    minimum: int | None = Field(default=None, ge=0)
    maximum: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> SalaryTargets:
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("salary minimum must not exceed maximum")
        return self


class BusinessProfile(BaseModel):
    """Profile data is user-owned and stored outside the repository."""

    model_config = ConfigDict(extra="forbid")

    business_name: str = ""
    owner_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    services: list[str] = Field(default_factory=list)
    home_city: str = ""
    home_state: str = ""
    radius_miles: int = Field(default=25, ge=1, le=500)
    target_verticals: list[str] = Field(default_factory=list)
    naics_codes: list[str] = Field(default_factory=list)
    set_aside_eligibility: list[str] = Field(default_factory=list)
    salary_targets: SalaryTargets = Field(default_factory=SalaryTargets)
    work_arrangements: list[str] = Field(default_factory=lambda: ["remote", "hybrid", "onsite"])
    timezone: str = "America/New_York"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown time zone: {value}") from exc
        return value

    @field_validator("naics_codes")
    @classmethod
    def validate_naics(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            code = value.strip()
            if not code.isdigit() or len(code) not in {2, 3, 4, 5, 6}:
                raise ValueError(f"invalid NAICS code: {value}")
            cleaned.append(code)
        return list(dict.fromkeys(cleaned))


def load_profile(path: Path) -> BusinessProfile:
    if not path.exists():
        return BusinessProfile()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("profile must contain a YAML mapping")
    return BusinessProfile.model_validate(raw)


def save_profile(profile: BusinessProfile, path: Path) -> None:
    """Atomically save a profile with owner-only permissions where supported."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(profile.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
    fd, temp_name = tempfile.mkstemp(prefix=".profile-", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, 0o600)
        Path(temp_name).replace(path)
        os.chmod(path, 0o600)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
