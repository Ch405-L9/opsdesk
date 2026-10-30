"""A synthetic in-memory candidate dossier.

Entirely invented. It is not any real person's dossier and carries no contact details, no
ownership facts, and no years-of-experience figure. Tests use this rather than reading any
canonical document, so no test depends on canonical content that only the owner may change.
"""

from vetted.core.domain.candidate import (
    CandidateDossier,
    EmploymentEvidence,
    ProjectEvidence,
    SkillEvidence,
    TrainingEvidence,
    WorkPreferences,
)
from vetted.core.enums import EvidenceTier

__all__ = ["synthetic_dossier"]


def synthetic_dossier() -> CandidateDossier:
    """Return an invented dossier for deterministic tests."""
    return CandidateDossier(
        name="Test Candidate",
        base_location="Testville, Test State, United States",
        preferences=WorkPreferences(
            target_country="United States",
            remote_preference="Preferred",
            relocation_willing=True,
            relocation_assistance_preferred=True,
            preferred_base_salary_min_usd=90_000,
            exclusion_floor_base_salary_usd=80_000,
        ),
        positioning_statement="Applied engineer building reliable, evidence-based tooling.",
        target_role_families=("Applied AI Engineer", "AI Integration Engineer"),
        avoid_role_families=("Research Scientist", "Principal Engineer"),
        verified_skills=(
            SkillEvidence(name="Python", tier=EvidenceTier.TIER_1_VERIFIED_SKILL),
            SkillEvidence(name="FastAPI", tier=EvidenceTier.TIER_1_VERIFIED_SKILL),
        ),
        project_evidence=(
            ProjectEvidence(
                name="Synthetic Retrieval Project",
                technologies=("Sample Vector Store", "Sample Lexical Index"),
                summary="Invented project used only to exercise tier-2 evidence handling.",
                qualifier="Controlled project evaluation; not production performance.",
            ),
        ),
        employment_evidence=(
            EmploymentEvidence(
                title="Test Engineer",
                organization="Synthetic Systems",
                location="Testville, Test State",
                start="January 2020",
                end="Present",
                technologies=("Linux", "Bash"),
                responsibilities=("Invented responsibility used only for tests.",),
            ),
        ),
        training_evidence=(
            TrainingEvidence(name="Sample Coursework", provider="Synthetic Academy"),
        ),
        prohibited_inferences=(
            "Completed degree",
            "Active clearance",
            "Total years of professional experience",
        ),
    )
