"""Load the user's approved dossier from a private YAML file.

The default path sits under gitignored `data/candidate/`. The package itself carries no
candidate facts. The file is validated by the frozen `CandidateDossier` model, so an unknown
field, such as a contact detail, fails loading instead of being kept.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from vetted.core.domain.candidate import CandidateDossier

__all__ = ["DEFAULT_DOSSIER_PATH", "DossierError", "load_dossier", "parse_dossier"]

DEFAULT_DOSSIER_PATH = Path("data/candidate/dossier.yaml")


class DossierError(ValueError):
    """The dossier file is missing, malformed, or fails validation."""


def parse_dossier(raw: Any) -> tuple[CandidateDossier, dict[str, tuple[str, ...]]]:
    """Validate a parsed YAML mapping into a dossier and its explicit skill terms."""
    if not isinstance(raw, dict):
        raise DossierError("The dossier must be a YAML mapping at the top level.")
    data = dict(raw)
    explicit_raw = data.pop("explicit_skill_terms", None) or {}
    if not isinstance(explicit_raw, dict):
        raise DossierError("explicit_skill_terms must map a skill name to a list of terms.")
    explicit = {str(k): tuple(str(t) for t in v) for k, v in explicit_raw.items()}
    try:
        dossier = CandidateDossier.model_validate(data)
    except ValidationError as exc:
        raise DossierError(f"Invalid dossier: {exc}") from exc
    unknown = set(explicit) - {skill.name for skill in dossier.verified_skills}
    if unknown:
        raise DossierError(
            f"explicit_skill_terms names skills that are not verified: {sorted(unknown)}"
        )
    return dossier, explicit


def load_dossier(
    path: Path | None = None,
) -> tuple[CandidateDossier, dict[str, tuple[str, ...]]]:
    """Read and validate the dossier file at `path` (default: `DEFAULT_DOSSIER_PATH`)."""
    path = path if path is not None else DEFAULT_DOSSIER_PATH
    if not path.is_file():
        raise DossierError(
            f"No dossier at {path}. Copy config/examples/dossier.example.yaml there and edit it."
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DossierError(f"Invalid YAML in {path}: {exc}") from exc
    return parse_dossier(raw)
