"""Domain-model invariants: frozen, closed, and tier-mandatory."""

import pytest
from pydantic import ValidationError

from fixtures.dossier_synthetic import synthetic_dossier
from vetted.core.domain import UNKNOWN
from vetted.core.domain.assessment import (
    GAP_FLAG,
    PARTIAL_CREDIT_TIERS,
    Assessment,
    TechnologyAlignmentResult,
    TechnologyGap,
    TechnologyMatch,
)
from vetted.core.domain.candidate import WorkPreferences
from vetted.core.domain.job import (
    CompanyFacts,
    CompensationFacts,
    JobProvenance,
    NormalizedJob,
    WorkArrangementFacts,
)
from vetted.core.enums import (
    EvidenceTier,
    MatchClassification,
    MatchMethod,
    Recommendation,
    RequirementKind,
    RiskFlag,
    TechnologyGapReason,
    ValidationStatus,
)


def test_candidate_dossier_is_frozen() -> None:
    dossier = synthetic_dossier()
    with pytest.raises(ValidationError):
        dossier.name = "Changed"  # type: ignore[misc]


def test_domain_models_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        CompanyFacts(company_name="Synthetic Systems", surprise_field="x")  # type: ignore[call-arg]


def _match(**overrides: object) -> dict[str, object]:
    """A fully disclosed exact match. Every A-6 audit value is present."""
    payload: dict[str, object] = {
        "technology": "Python",
        "raw_job_phrase": "Python",
        "normalized_job_identifier": "PYTHON",
        "raw_candidate_evidence_phrase": "Python",
        "normalized_candidate_identifier": "PYTHON",
        "match_method": MatchMethod.EXACT,
        "alias_family_identifier": None,
        "requirement_kind": RequirementKind.REQUIRED,
        "tier": EvidenceTier.TIER_1_VERIFIED_SKILL,
        "evidence_reference": "Verified skills - Software and automation",
    }
    payload.update(overrides)
    return payload


def test_technology_match_requires_a_tier() -> None:
    """D-7: an untiered technology match must be unconstructable."""
    payload = _match()
    del payload["tier"]
    with pytest.raises(ValidationError):
        TechnologyMatch.model_validate(payload)

    match = TechnologyMatch.model_validate(_match())
    assert match.tier is EvidenceTier.TIER_1_VERIFIED_SKILL


@pytest.mark.parametrize(
    "field",
    [
        "technology",
        "raw_job_phrase",
        "normalized_job_identifier",
        "raw_candidate_evidence_phrase",
        "normalized_candidate_identifier",
        "match_method",
        "alias_family_identifier",
        "requirement_kind",
        "tier",
        "evidence_reference",
    ],
)
def test_every_audit_value_is_mandatory(field: str) -> None:
    """E-5, A-6: a match that cannot be fully disclosed must be unconstructable."""
    payload = _match()
    del payload[field]
    with pytest.raises(ValidationError):
        TechnologyMatch.model_validate(payload)


@pytest.mark.parametrize(
    "field",
    [
        "technology",
        "raw_job_phrase",
        "normalized_job_identifier",
        "raw_candidate_evidence_phrase",
        "normalized_candidate_identifier",
        "evidence_reference",
    ],
)
def test_blank_audit_value_is_rejected(field: str) -> None:
    """A present-but-empty field discloses nothing."""
    with pytest.raises(ValidationError, match="must not be blank"):
        TechnologyMatch.model_validate(_match(**{field: "   "}))


def test_alias_match_must_name_its_alias_family() -> None:
    """A-6: the audit trail records which alias row fired."""
    with pytest.raises(ValidationError, match="must name what produced it"):
        TechnologyMatch.model_validate(
            _match(match_method=MatchMethod.ALIAS, alias_family_identifier=None)
        )
    match = TechnologyMatch.model_validate(
        _match(
            technology="React",
            raw_job_phrase="React.js",
            normalized_job_identifier="REACT",
            raw_candidate_evidence_phrase="React",
            normalized_candidate_identifier="REACT",
            match_method=MatchMethod.ALIAS,
            alias_family_identifier="REACT",
        )
    )
    assert match.match_method is MatchMethod.ALIAS
    assert match.alias_family_identifier == "REACT"


def test_exact_match_may_not_claim_an_alias_family() -> None:
    with pytest.raises(ValidationError, match="has no alias family"):
        TechnologyMatch.model_validate(_match(alias_family_identifier="REACT"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("match_method", "FUZZY"),
        ("match_method", "SEMANTIC"),
        ("match_method", "SUBSTRING"),
        ("requirement_kind", "DESIRABLE"),
        ("requirement_kind", "OPTIONAL"),
    ],
)
def test_unapproved_match_members_are_rejected(field: str, value: str) -> None:
    """A-6 bars fuzzy, semantic, and substring matching, so no such member exists."""
    with pytest.raises(ValidationError):
        TechnologyMatch.model_validate(_match(**{field: value}))


def test_technology_match_is_frozen() -> None:
    match = TechnologyMatch.model_validate(_match())
    with pytest.raises(ValidationError):
        match.tier = EvidenceTier.TIER_4_TRAINING  # type: ignore[misc]


# ------------------------------------------------------------------- technology gaps


def test_gap_flag_is_the_only_flag_a_gap_raises() -> None:
    """A-5 through A-7 invent no RiskFlag member."""
    assert GAP_FLAG is RiskFlag.REQUIRED_SKILL_GAP
    assert {
        EvidenceTier.TIER_2_PROJECT_EVIDENCE,
        EvidenceTier.TIER_4_TRAINING,
    } == PARTIAL_CREDIT_TIERS


def test_gap_is_always_a_required_slot() -> None:
    """A-7: preferred technologies never raise a gap."""
    gap = TechnologyGap(
        raw_job_phrase="Kubernetes",
        normalized_job_identifier=None,
        reason=TechnologyGapReason.UNRECOGNIZED_TERM,
        best_tier_found=None,
    )
    assert gap.requirement_kind is RequirementKind.REQUIRED
    with pytest.raises(ValidationError):
        TechnologyGap.model_validate(
            {
                "raw_job_phrase": "Kubernetes",
                "normalized_job_identifier": None,
                "requirement_kind": RequirementKind.PREFERRED,
                "reason": TechnologyGapReason.NO_EVIDENCE,
                "best_tier_found": None,
            }
        )


def test_unrecognized_term_carries_no_normalized_identifier() -> None:
    """A-6: the normalized identifier is null when the phrase is unrecognized."""
    with pytest.raises(ValidationError, match="no normalized identifier"):
        TechnologyGap(
            raw_job_phrase="Weaviate",
            normalized_job_identifier="WEAVIATE",
            reason=TechnologyGapReason.UNRECOGNIZED_TERM,
            best_tier_found=None,
        )


@pytest.mark.parametrize(
    "reason",
    [TechnologyGapReason.NO_EVIDENCE, TechnologyGapReason.UNRECOGNIZED_TERM],
)
def test_no_evidence_gap_may_not_claim_a_tier(reason: TechnologyGapReason) -> None:
    """E-4: no evidence means no tier was found."""
    with pytest.raises(ValidationError, match="no evidence was found"):
        TechnologyGap.model_validate(
            {
                "raw_job_phrase": "Terraform",
                "normalized_job_identifier": None,
                "reason": reason,
                "best_tier_found": EvidenceTier.TIER_1_VERIFIED_SKILL,
            }
        )


def test_partial_credit_gap_requires_tier_2_or_tier_4() -> None:
    """E-7: partial credit still raises the gap, and only for these tiers."""
    gap = TechnologyGap(
        raw_job_phrase="Kotlin",
        normalized_job_identifier="KOTLIN",
        reason=TechnologyGapReason.TIER_2_OR_TIER_4_ONLY,
        best_tier_found=EvidenceTier.TIER_2_PROJECT_EVIDENCE,
    )
    assert gap.best_tier_found is EvidenceTier.TIER_2_PROJECT_EVIDENCE

    with pytest.raises(ValidationError, match="only to Tier 2 or Tier 4"):
        TechnologyGap(
            raw_job_phrase="Kotlin",
            normalized_job_identifier="KOTLIN",
            reason=TechnologyGapReason.TIER_2_OR_TIER_4_ONLY,
            best_tier_found=EvidenceTier.TIER_3_EMPLOYMENT_EVIDENCE,
        )


def test_prohibited_inference_gap_records_the_tier_it_refused() -> None:
    """E-6: a Tier 3 match may not satisfy a prohibited-inference requirement."""
    gap = TechnologyGap(
        raw_job_phrase="AWS",
        normalized_job_identifier="AWS",
        reason=TechnologyGapReason.PROHIBITED_INFERENCE,
        best_tier_found=EvidenceTier.TIER_3_EMPLOYMENT_EVIDENCE,
    )
    assert gap.best_tier_found is EvidenceTier.TIER_3_EMPLOYMENT_EVIDENCE

    with pytest.raises(ValidationError, match="requires the tier that was found"):
        TechnologyGap(
            raw_job_phrase="AWS",
            normalized_job_identifier="AWS",
            reason=TechnologyGapReason.PROHIBITED_INFERENCE,
            best_tier_found=None,
        )


# ------------------------------------------------------- the dimension-result boundary


def _result(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "job_id": "synthetic-1",
        "dimension": "verified_technical_skill_alignment",
        "dimension_weight": 20,
        "required_slot_count": 2,
        "multiplier_sum": 1.00,
        "points": 10.00,
        "matches": (TechnologyMatch.model_validate(_match()),),
        "gaps": (
            TechnologyGap(
                raw_job_phrase="Weaviate",
                normalized_job_identifier=None,
                reason=TechnologyGapReason.UNRECOGNIZED_TERM,
                best_tier_found=None,
            ),
        ),
    }
    payload.update(overrides)
    return payload


def test_dimension_result_carries_no_assessment_verdict() -> None:
    """Ruling 2: the dimension path cannot emit a score, classification, or recommendation."""
    fields = set(TechnologyAlignmentResult.model_fields)
    for forbidden in (
        "score",
        "classification",
        "recommendation",
        "validation_status",
        "blockers",
        "risk_flags",
        "compensation",
    ):
        assert forbidden not in fields, f"the dimension result must not carry {forbidden!r}"


def test_dimension_result_holds_the_worked_example() -> None:
    """A-5: Weaviate plus Python with Python evidence is 20 x 1.00 / 2, exact."""
    result = TechnologyAlignmentResult.model_validate(_result())
    assert result.points == 10.00
    assert result.required_slot_count == 2
    assert len(result.gaps) == 1


def test_dimension_result_is_frozen() -> None:
    result = TechnologyAlignmentResult.model_validate(_result())
    with pytest.raises(ValidationError):
        result.points = 20.0  # type: ignore[misc]


def test_dimension_points_may_not_exceed_the_dimension_weight() -> None:
    """E-1: multipliers are capped at the dimension weight."""
    with pytest.raises(ValidationError, match=r"must lie in \[0, 20\]"):
        TechnologyAlignmentResult.model_validate(
            _result(required_slot_count=1, multiplier_sum=1.0, points=20.01, gaps=())
        )


def test_zero_required_slots_scores_exactly_zero() -> None:
    """A-5: and raises no gap, because nothing was required."""
    result = TechnologyAlignmentResult.model_validate(
        _result(required_slot_count=0, multiplier_sum=0.0, points=0.0, matches=(), gaps=())
    )
    assert result.points == 0.0

    with pytest.raises(ValidationError, match="scores exactly 0 points"):
        TechnologyAlignmentResult.model_validate(
            _result(required_slot_count=0, multiplier_sum=0.0, points=4.0, matches=(), gaps=())
        )


def test_zero_required_slots_may_not_carry_a_gap() -> None:
    with pytest.raises(ValidationError, match="raises no gap"):
        TechnologyAlignmentResult.model_validate(
            _result(required_slot_count=0, multiplier_sum=0.0, points=0.0, matches=())
        )


def test_multiplier_sum_may_not_exceed_the_slot_count() -> None:
    """No approved multiplier exceeds 1.00."""
    with pytest.raises(ValidationError, match="cannot exceed the slot count"):
        TechnologyAlignmentResult.model_validate(
            _result(required_slot_count=1, multiplier_sum=1.5, points=20.0, gaps=())
        )


def test_a_preferred_match_may_not_enter_the_dimension() -> None:
    """A-7: required technologies are the only input to this dimension."""
    preferred = TechnologyMatch.model_validate(
        _match(requirement_kind=RequirementKind.PREFERRED)
    )
    with pytest.raises(ValidationError, match="only required technologies"):
        TechnologyAlignmentResult.model_validate(_result(matches=(preferred,)))


def test_dimension_name_is_fixed() -> None:
    with pytest.raises(ValidationError):
        TechnologyAlignmentResult.model_validate(_result(dimension="role_family_relevance"))


def test_work_authorization_accepts_only_unknown() -> None:
    """D-5: no authorization value may be stored in tracked project data."""
    preferences = WorkPreferences(
        target_country="United States",
        remote_preference="Preferred",
        relocation_willing=True,
        relocation_assistance_preferred=True,
        preferred_base_salary_min_usd=90_000,
        exclusion_floor_base_salary_usd=80_000,
    )
    assert preferences.work_authorization == UNKNOWN

    with pytest.raises(ValidationError):
        WorkPreferences(
            target_country="United States",
            remote_preference="Preferred",
            relocation_willing=True,
            relocation_assistance_preferred=True,
            preferred_base_salary_min_usd=90_000,
            exclusion_floor_base_salary_usd=80_000,
            work_authorization="AUTHORIZED",  # type: ignore[arg-type]
        )


def test_absent_listing_values_default_to_unknown() -> None:
    job = NormalizedJob(
        job_id="synthetic-1",
        job_title="Applied Engineer",
        provenance=JobProvenance(source_platform="wellfound"),
        company=CompanyFacts(company_name="Synthetic Systems"),
        work=WorkArrangementFacts(),
        compensation=CompensationFacts(),
    )
    assert job.company.company_website == UNKNOWN
    assert job.compensation.base_salary_min_usd == UNKNOWN
    assert job.education_requirements == UNKNOWN
    assert job.required_technologies == ()


def test_assessment_defaults_carry_no_score() -> None:
    """Phase 1A has no scoring, so an assessment must be constructable without one."""
    assessment = Assessment(
        job_id="synthetic-1",
        validation_status=ValidationStatus.INSUFFICIENT_EVIDENCE,
        classification=MatchClassification.INSUFFICIENT_EVIDENCE,
        recommendation=Recommendation.HOLD_FOR_MISSING_COMPENSATION_OR_LOCATION,
    )
    assert assessment.score is None
    assert assessment.blockers == ()
    assert assessment.compensation is None
