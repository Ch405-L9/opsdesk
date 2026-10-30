"""Frozen domain models.

Every model in this package is immutable and forbids unknown fields. No model carries a
contact field (D-9), a business-ownership field (D-2), or a candidate total-years-of-experience
field (D-4).
"""

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

UNKNOWN: Final = "UNKNOWN"
"""The single sentinel for an absent listing value. Never converted to a concrete value."""

Unknown = Literal["UNKNOWN"]
"""Type of the UNKNOWN sentinel, so absence is representable in the type system."""


class FrozenModel(BaseModel):
    """Immutable base for every domain model."""

    model_config = ConfigDict(frozen=True, extra="forbid")


__all__ = ["UNKNOWN", "FrozenModel", "Unknown"]
