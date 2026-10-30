"""The dossier comes from a user file; the package itself holds no candidate facts."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from fixtures.dossier_synthetic import synthetic_dossier
from vetted.core.dossier import candidate_terms, load_dossier, parse_dossier
from vetted.core.dossier.loader import DossierError
from vetted.core.enums import EvidenceTier

REPO_ROOT = Path(__file__).resolve().parents[3]


def _raw() -> dict[str, object]:
    return synthetic_dossier().model_dump(mode="json")


def test_example_dossier_loads(repo_root: Path) -> None:
    dossier, explicit = load_dossier(repo_root / "config" / "examples" / "dossier.example.yaml")
    assert dossier.name == "Test Candidate"
    assert explicit == {"Python": ("Python 3",)}


def test_missing_file_names_the_example() -> None:
    with pytest.raises(DossierError, match="dossier.example.yaml"):
        load_dossier(Path("does/not/exist.yaml"))


def test_contact_field_is_rejected() -> None:
    raw = _raw()
    raw["email"] = "someone@example.com"
    with pytest.raises(DossierError):
        parse_dossier(raw)


def test_explicit_terms_must_name_a_verified_skill() -> None:
    raw = _raw()
    raw["explicit_skill_terms"] = {"Cobol": ["COBOL-85"]}
    with pytest.raises(DossierError, match="not verified"):
        parse_dossier(raw)


def test_terms_follow_the_evidence_tiers() -> None:
    dossier, _ = parse_dossier(_raw())
    by_term = {t.term: t for t in candidate_terms(dossier)}
    assert by_term["Python"].tier is EvidenceTier.TIER_1_VERIFIED_SKILL
    assert by_term["Sample Vector Store"].tier is EvidenceTier.TIER_2_PROJECT_EVIDENCE
    assert by_term["Linux"].tier is EvidenceTier.TIER_3_EMPLOYMENT_EVIDENCE
    assert by_term["Linux"].evidence_reference.startswith("Dossier: employment")


def test_explicit_terms_inherit_the_skill_tier_and_reference() -> None:
    dossier, explicit = parse_dossier({**_raw(), "explicit_skill_terms": {"Python": ["Py"]}})
    extra = [t for t in candidate_terms(dossier, explicit) if t.term == "Py"]
    assert extra and extra[0].tier is EvidenceTier.TIER_1_VERIFIED_SKILL
    assert extra[0].evidence_reference == "Dossier: verified skill 'Python'"


def test_default_path_is_gitignored(repo_root: Path) -> None:
    ignore = (repo_root / ".gitignore").read_text(encoding="utf-8")
    assert "data/candidate/dossier.yaml" in ignore


def test_round_trip_yaml(tmp_path: Path) -> None:
    path = tmp_path / "d.yaml"
    path.write_text(yaml.safe_dump(_raw()), encoding="utf-8")
    dossier, _ = load_dossier(path)
    assert dossier == synthetic_dossier()
