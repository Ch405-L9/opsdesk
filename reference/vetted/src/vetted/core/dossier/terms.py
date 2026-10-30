"""Candidate evidence terms derived from a dossier.

Replaces careerops' hard-coded transcription: the same tiers and the same "no normalization
here" rule, but the terms come from whichever dossier the user approved.
"""

from collections.abc import Mapping
from typing import NamedTuple

from vetted.core.domain.candidate import CandidateDossier
from vetted.core.enums import EvidenceTier

__all__ = ["CandidateTerm", "candidate_terms"]


class CandidateTerm(NamedTuple):
    """One candidate evidence term, its tier, and the dossier entry a report must cite.

    `term` is the raw phrase exactly as the dossier states it, or an explicit term the user
    attached to a verified skill. Normalization belongs to the matcher, not here.
    """

    term: str
    tier: EvidenceTier
    evidence_reference: str


def candidate_terms(
    dossier: CandidateDossier,
    explicit_skill_terms: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[CandidateTerm, ...]:
    """Every candidate technology term available for matching, with tier and citation.

    Verified skills keep the tier the dossier gives them, project technologies are Tier 2,
    and employment technologies Tier 3. Training yields nothing, because `TrainingEvidence`
    carries no technologies. A term may repeat at different tiers; best tier wins in the
    matcher.
    """
    explicit = explicit_skill_terms or {}
    terms: list[CandidateTerm] = []
    for skill in dossier.verified_skills:
        reference = f"Dossier: verified skill '{skill.name}'"
        terms.append(CandidateTerm(skill.name, skill.tier, reference))
        for extra in explicit.get(skill.name, ()):
            terms.append(CandidateTerm(extra, skill.tier, reference))
    for project in dossier.project_evidence:
        reference = f"Dossier: project '{project.name}'"
        for technology in project.technologies:
            terms.append(
                CandidateTerm(technology, EvidenceTier.TIER_2_PROJECT_EVIDENCE, reference)
            )
    for job in dossier.employment_evidence:
        reference = f"Dossier: employment '{job.title}, {job.organization}'"
        for technology in job.technologies:
            terms.append(
                CandidateTerm(technology, EvidenceTier.TIER_3_EMPLOYMENT_EVIDENCE, reference)
            )
    return tuple(terms)
