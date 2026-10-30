"""Deterministic scoring.

One dimension is implemented: `verified_technical_skill_alignment`, per the approved A-5
formula. It returns a `TechnologyAlignmentResult`, which carries no total score, no
`MatchClassification`, no `Recommendation`, and no `ValidationStatus`, so a dimension figure
can never become a full assessment while the readiness gate stands.

Everything else remains a signature. `assess_job` and `assess_compensation` still raise, and
still require `load_ready_assessment_config`, which refuses while any of the five remaining
policy keys is UNRESOLVED. Scoring never overrides a blocker.

Total years of experience is never calculated and never inferred from job dates (D-4).
"""

from vetted.core.assess.evidence import match_technologies, resolve_job_phrase
from vetted.core.config.schema import (
    APPROVED_ALLOCATION_DIMENSION,
    AssessmentConfig,
    CompensationConfig,
)
from vetted.core.domain.assessment import (
    Assessment,
    CompensationAssessment,
    TechnologyAlignmentResult,
)
from vetted.core.domain.candidate import CandidateDossier
from vetted.core.domain.job import NormalizedJob
from vetted.core.dossier.terms import CandidateTerm
from vetted.core.enums import MatchMethod

__all__ = ["assess_compensation", "assess_job", "score_technology_alignment"]


def score_technology_alignment(
    job_id: str,
    required_technologies: tuple[str, ...],
    terms: tuple[CandidateTerm, ...],
    config: AssessmentConfig,
) -> TechnologyAlignmentResult:
    """Score the verified_technical_skill_alignment dimension by the approved A-5 formula.

        points = 20 × (sum of required-slot best-tier multipliers) / number of required slots
        points = 0                                                  when there are none

    Required slots are counted after normalization and deduplication by resolved identifier.
    Any-of grouping is not applied: the capture format carries no any-of marker, so each
    entry is one slot until a grouped requirement source exists.

    Preferred technologies are accepted nowhere in this call: they enter neither the numerator
    nor the denominator (A-5), and preferred extraction is deferred (A-7).

    `terms` is the candidate evidence index, normally `candidate_terms(dossier)`. It is passed
    rather than fetched so the dependency is explicit and testable with synthetic terms.

    `points` is exact and unrounded. Rounding remains the unresolved `score_rounding_rule`, so
    this function never rounds, truncates, or clamps.

    Takes the structurally validated configuration. It does not call
    `load_ready_assessment_config`, because a single dimension is not a full assessment; that
    gate still guards `assess_job`.
    """
    policy = config.scoring.technology_base_credit_allocation
    weight = config.scoring.weights[policy.dimension]
    multipliers = config.scoring.evidence_tier_weighting
    normalization = config.scoring.technology_matching_normalization

    slots: list[str] = []
    for phrase in required_technologies:
        if not phrase.strip():
            continue
        identifier, _, _ = resolve_job_phrase(phrase, normalization)
        if identifier not in slots:
            slots.append(identifier)

    categories = config.scoring.technology_categories
    credit = categories.substitution_credit
    matches, gaps = match_technologies(
        required_technologies, terms, normalization, categories
    )
    multiplier_sum = sum(
        getattr(multipliers, match.tier.value)
        * (
            credit.substitute
            if match.match_method is MatchMethod.CATEGORY_SUBSTITUTE
            else credit.direct
        )
        for match in matches
    )

    slot_count = len(slots)
    points = (
        weight * multiplier_sum / slot_count
        if slot_count >= 1
        else float(policy.zero_required_slots_points)
    )

    return TechnologyAlignmentResult(
        job_id=job_id,
        dimension=APPROVED_ALLOCATION_DIMENSION,
        dimension_weight=weight,
        required_slot_count=slot_count,
        multiplier_sum=multiplier_sum,
        points=points,
        matches=matches,
        gaps=gaps,
    )


def assess_compensation(
    job: NormalizedJob,
    config: CompensationConfig,
) -> CompensationAssessment:
    """Classify the listing's compensation into an approved band (D-3, A-2).

    Hourly and contract compensation is never annualized. Absent compensation yields UNKNOWN
    and MISSING_COMPENSATION, never a rejection.
    """
    raise NotImplementedError(
        "Compensation assessment is Phase 3 work and is not approved. The approved bands are "
        "in config/compensation.yaml (D-3, A-2)."
    )


def assess_job(
    job: NormalizedJob,
    dossier: CandidateDossier,
    config: AssessmentConfig,
) -> Assessment:
    """Produce a complete assessment.

    Callers must obtain `config` from `load_ready_assessment_config`, which refuses to return
    a configuration while any policy key is UNRESOLVED.
    """
    raise NotImplementedError(
        "Full job assessment is not approved. Five policy keys still gate readiness: "
        "seniority_band_selection_precedence, compensation_range_selection_rule, "
        "critical_unknown_detection_rule, score_rounding_rule, and "
        "report_and_cli_score_display_scope. Use score_technology_alignment for the one "
        "approved dimension."
    )
