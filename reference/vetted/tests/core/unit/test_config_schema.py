"""Configuration schema tests, using in-memory configurations only."""

from typing import Any

import pytest
from pydantic import ValidationError

from vetted.core.config.schema import (
    APPROVED_ALIAS_FAMILIES,
    APPROVED_ALIAS_FAMILY_COUNT,
    APPROVED_ALIAS_VARIANT_COUNT,
    APPROVED_CANONICAL_TECHNOLOGIES,
    REQUIRED_UNRESOLVED_POLICY_KEYS,
    UNRESOLVED,
    AliasFamily,
    AssessmentPolicyUnresolvedError,
    BlockerConfig,
    CanonicalTechnology,
    ClassificationThresholds,
    CompensationConfig,
    EvidenceTierWeights,
    MarketReference,
    RegionalPriceParity,
    ReportDisplayPolicy,
    RequiredPreferredPolicy,
    RiskFlagConfig,
    SalaryTargets,
    ScoringConfig,
    SeniorityBands,
    SeniorScopeRule,
    TechnologyAllocationPolicy,
    TechnologyCategories,
    TechnologyNormalizationPolicy,
)
from vetted.core.enums import BlockerCode, RiskFlag

VALID_WEIGHTS: dict[str, int] = {
    "role_family_relevance": 20,
    "verified_technical_skill_alignment": 20,
    "responsibility_and_project_evidence_alignment": 15,
    "seniority_and_documented_evidence_compatibility": 15,
    "compensation_compatibility": 10,
    "location_remote_relocation_compatibility": 8,
    "employment_type_compatibility": 5,
    "employer_listing_validation_quality": 4,
    "growth_learning_relevance": 3,
}

VALID_TIER_WEIGHTS: dict[str, float] = {
    "TIER_1_VERIFIED_SKILL": 1.00,
    "TIER_2_PROJECT_EVIDENCE": 0.70,
    "TIER_3_EMPLOYMENT_EVIDENCE": 0.90,
    "TIER_4_TRAINING": 0.30,
}

VALID_THRESHOLDS: dict[str, Any] = {
    "bands": [
        {"classification": "STRONG_MATCH", "min_score": 72, "max_score": 100},
        {"classification": "PLAUSIBLE_MATCH", "min_score": 58, "max_score": 71},
        {"classification": "STRETCH", "min_score": 42, "max_score": 57},
        {"classification": "AVOID", "min_score": 0, "max_score": 41},
    ]
}

VALID_SENIORITY: dict[str, Any] = {
    "bands": [
        {"points": 15, "description": "intermediate"},
        {"points": 11, "description": "mid-level with one moderate gap"},
        {"points": 7, "description": "broad or unclear"},
        {"points": 3, "description": "explicit 5+ years"},
        {"points": 0, "description": "materially unsupported senior scope"},
    ]
}

VALID_REPORT_DISPLAY: dict[str, Any] = {
    "order": [
        "Recommendation",
        "Hard blockers",
        "Validation status and risk flags",
        "Critical unknowns / missing evidence",
        "Match classification and score",
        "Per-dimension score breakdown",
        "Evidence-tier map with candidate-proof references",
        "Human next action",
    ],
    "score_never_headline": True,
}

VALID_SENIOR_SCOPE: dict[str, Any] = {
    "requires_explicit_senior_scope": True,
    "minimum_unsupported_requirements": 2,
    "senior_title_tokens": ["Senior", "Staff", "Principal", "Lead", "Head"],
    "unsupported_requirement_categories": [
        "leadership_or_ownership",
        "five_plus_years_required",
        "mlops_cloud_or_platform_ownership",
        "kubernetes_terraform_docker_core",
        "research_training_or_publications",
        "unsupported_scale_or_ownership_claims",
        "clearance_or_independent_blocker",
    ],
}


VALID_ALLOCATION: dict[str, Any] = {
    "dimension": "verified_technical_skill_alignment",
    "allocation": "required_only_conservative",
    "zero_required_slots_points": 0,
    "preferred_in_numerator": False,
    "preferred_in_denominator": False,
    "unrecognized_required_term_credit": 0.00,
    "unrecognized_required_term_stays_in_denominator": True,
    "numerator_source": "structured_technology_fields_only",
    "prose_token_scanning": False,
    "rounding": "deferred_to_score_rounding_rule",
}

VALID_NORMALIZATION: dict[str, Any] = {
    "normalization_steps": ["nfc", "casefold", "collapse_whitespace", "trim"],
    "whole_phrase_only": True,
    "alias_direction": "variant_to_canonical",
    "unknown_alias_auto_match": False,
    "bare_two_letter_aliases_allowed": False,
    "candidate_side_compound_parsing": "deferred",
    "unknown_term_handling": "report_section_only",
    "persistent_review_queue": False,
    "canonical_technologies": [
        {"id": identifier, "display_name": display}
        for identifier, display in APPROVED_CANONICAL_TECHNOLOGIES
    ],
    "alias_families": [
        {
            "canonical_id": identifier,
            "approval_date": "2026-09-26",
            "defense": "same technology, not a related one",
            "variants": list(variants),
        }
        for identifier, variants in APPROVED_ALIAS_FAMILIES
    ],
    "deferred_alias_variants": [
        "crontab",
        "openssh",
        "js/ts",
        "javascript/typescript",
        "js",
        "ts",
        "react native",
        "ubuntu",
        "vector database",
    ],
    "deferred_alias_mappings": ["RAG -> LangChain", "MCP -> Azure OpenAI"],
    "deferred_alias_categories": ["broad_category", "capability_phrase"],
}

VALID_REQUIRED_PREFERRED: dict[str, Any] = {
    "required_only_dimension_input": True,
    "preferred_score_effect": "none",
    "preferred_classification_effect": "none",
    "preferred_recommendation_effect": "none",
    "preferred_flag_effect": "none",
    "preferred_raises_required_skill_gap": False,
    "preferred_evidence_map_required": True,
    "preferred_influences_human_next_action_wording_only": True,
    "no_explicit_required_technologies_points": 0,
    "any_of_slot_count": 1,
    "equivalent_may_introduce_new_technology": False,
    "generic_wording_becomes_slot": False,
    "critical_unknown_when_structured_field_yields_no_technology": True,
    "compound_all_of_slot": "deferred",
    "preferred_extraction": "deferred",
}

VALID_CATEGORIES: dict[str, Any] = {
    "substitution_credit": {"direct": 1.00, "substitute": 0.50, "none": 0.00},
    "categories": [
        {
            "name": "CRM_TICKETING",
            "substitutable": True,
            "note": "Employee-facing CRM and ticketing systems.",
            "members": ["Salesforce", "Monday", "Freshdesk"],
        },
        {
            "name": "PROGRAMMING_LANGUAGE",
            "substitutable": False,
            "note": "General-purpose languages, not interchangeable.",
            "members": ["Python", "Rust", "Go"],
        },
    ],
}

VALID_SALARY_TARGETS: dict[str, Any] = {
    "hard_floor_usd": 70000,
    "soft_minimum_usd": 85000,
    "market_target_usd": 120000,
    "status": "PROVISIONAL",
    "decided_on": "2026-09-26",
    "note": "Invented targets used only for tests.",
}

VALID_MARKET_REFERENCE: dict[str, Any] = {
    "status": "PROVISIONAL",
    "rows": [
        {
            "label": "invented_median_annual_usd",
            "value": 100000,
            "as_of": "2025-05",
            "source": "https://example.invalid/source",
            "note": "Invented figure used only for tests.",
        }
    ],
}

VALID_RPP: dict[str, Any] = {
    "status": "PROVISIONAL",
    "us_average": 100,
    "as_of": "2024",
    "source": "https://example.invalid/rpp",
    "candidate_state": "GA",
    "apply_only_on_relocation": True,
    "states": {"GA": 96.3, "CA": 110.7},
    "note": "Invented parities used only for tests.",
}

VALID_ALIAS_FAMILY: dict[str, Any] = {
    "canonical_id": "REACT",
    "approval_date": "2026-09-26",
    "defense": "Spelling variants of the identical library",
    "variants": ["react.js", "reactjs"],
}


def _normalization(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        key: (list(value) if isinstance(value, list) else value)
        for key, value in VALID_NORMALIZATION.items()
    }
    payload.update(overrides)
    return payload


def _unresolved_policy(resolved: set[str] | None = None) -> dict[str, Any]:
    """Build a gate block. `resolved` keys are given a non-sentinel value on purpose.

    Writing any value other than the UNRESOLVED sentinel is rejected by validation: that is
    the gate-integrity rule, not a limitation. Tests use this to prove the rejection.
    """
    done = resolved or set()
    return {
        key: ("approved" if key in done else UNRESOLVED)
        for key in REQUIRED_UNRESOLVED_POLICY_KEYS
    }


def _scoring(
    weights: dict[str, int] | None = None,
    unresolved_policy: dict[str, Any] | None = None,
) -> ScoringConfig:
    return ScoringConfig.model_validate(
        {
            "weights": weights if weights is not None else dict(VALID_WEIGHTS),
            "evidence_tier_weighting": dict(VALID_TIER_WEIGHTS),
            "match_classification_thresholds": VALID_THRESHOLDS,
            "seniority_bands": VALID_SENIORITY,
            "report_display": VALID_REPORT_DISPLAY,
            "technology_base_credit_allocation": dict(VALID_ALLOCATION),
            "technology_matching_normalization": _normalization(),
            "required_vs_preferred_technology_handling": dict(VALID_REQUIRED_PREFERRED),
            "technology_categories": VALID_CATEGORIES,
            "unresolved_policy": (
                unresolved_policy if unresolved_policy is not None else _unresolved_policy()
            ),
        }
    )


# --------------------------------------------------------------------------- weights


def test_weights_totalling_100_are_accepted() -> None:
    assert sum(_scoring().weights.values()) == 100


@pytest.mark.parametrize("delta", [-1, 1])
def test_weights_not_totalling_100_are_rejected(delta: int) -> None:
    weights = dict(VALID_WEIGHTS)
    weights["growth_learning_relevance"] += delta
    with pytest.raises(ValidationError):
        _scoring(weights)


def test_superseded_seniority_key_is_rejected() -> None:
    """D-4: the dimension was renamed; the old key must not load."""
    weights = dict(VALID_WEIGHTS)
    weights["seniority_years"] = weights.pop("seniority_and_documented_evidence_compatibility")
    with pytest.raises(ValidationError):
        _scoring(weights)


# ------------------------------------------------------------------ unresolved gate


def test_unresolved_keys_are_reported() -> None:
    """The gate reports the exact approved key set, in the approved order."""
    assert _scoring().unresolved_keys() == REQUIRED_UNRESOLVED_POLICY_KEYS


def test_unresolved_policy_key_set_must_be_exact() -> None:
    """A key cannot be dropped to unblock readiness, nor an extra key smuggled in."""
    short = _unresolved_policy()
    short.pop("score_rounding_rule")
    with pytest.raises(ValidationError):
        _scoring(unresolved_policy=short)

    extra = _unresolved_policy()
    extra["invented_key"] = UNRESOLVED
    with pytest.raises(ValidationError):
        _scoring(unresolved_policy=extra)


def test_a_key_cannot_be_released_by_changing_its_value() -> None:
    """Gate integrity: the UNRESOLVED sentinel is the only permitted value.

    Previously any non-sentinel string passed readiness, so "approved" or a typo silently
    released a key. Resolution now requires removing the key from `unresolved_policy` and from
    REQUIRED_UNRESOLVED_POLICY_KEYS together, plus a typed block carrying its own status.
    """
    with pytest.raises(ValidationError, match="only the 'UNRESOLVED' sentinel"):
        _scoring(unresolved_policy=_unresolved_policy({"score_rounding_rule"}))


def test_releasing_every_key_by_value_is_rejected_too() -> None:
    with pytest.raises(ValidationError, match="only the 'UNRESOLVED' sentinel"):
        _scoring(
            unresolved_policy=_unresolved_policy(set(REQUIRED_UNRESOLVED_POLICY_KEYS))
        )


@pytest.mark.parametrize("value", ["approved", "APPROVED", "PROVISIONAL", "", "unresolved", None])
def test_no_near_miss_value_passes_the_gate(value: object) -> None:
    """Case, whitespace, and near synonyms are all rejected. Only the exact sentinel passes."""
    gate = _unresolved_policy()
    gate["score_rounding_rule"] = value
    with pytest.raises(ValidationError):
        _scoring(unresolved_policy=gate)


def test_the_error_names_how_a_key_is_actually_resolved() -> None:
    """A rejection must tell the reader the correct procedure, not only that it failed."""
    gate = _unresolved_policy()
    gate["score_rounding_rule"] = "approved"
    with pytest.raises(ValidationError) as excinfo:
        _scoring(unresolved_policy=gate)
    message = str(excinfo.value)
    assert "REQUIRED_UNRESOLVED_POLICY_KEYS" in message
    assert "PolicyStatus" in message


def test_unresolved_error_names_every_key() -> None:
    error = AssessmentPolicyUnresolvedError(["a", "b"])
    assert error.unresolved_keys == ("a", "b")
    assert "a, b" in str(error)


# --------------------------------------------------------------- P-1 tier weighting


def test_tier_weights_require_every_tier() -> None:
    incomplete = dict(VALID_TIER_WEIGHTS)
    incomplete.pop("TIER_4_TRAINING")
    with pytest.raises(ValidationError):
        EvidenceTierWeights.model_validate(incomplete)


def test_tier_multiplier_above_one_is_rejected() -> None:
    weights = dict(VALID_TIER_WEIGHTS)
    weights["TIER_2_PROJECT_EVIDENCE"] = 1.2
    with pytest.raises(ValidationError):
        EvidenceTierWeights.model_validate(weights)


def test_tier_multiplier_of_zero_or_below_is_rejected() -> None:
    for bad in (0.0, -0.1):
        weights = dict(VALID_TIER_WEIGHTS)
        weights["TIER_4_TRAINING"] = bad
        with pytest.raises(ValidationError):
            EvidenceTierWeights.model_validate(weights)


def test_tier_1_must_be_the_reference_multiplier() -> None:
    weights = dict(VALID_TIER_WEIGHTS)
    weights["TIER_1_VERIFIED_SKILL"] = 0.95
    with pytest.raises(ValidationError):
        EvidenceTierWeights.model_validate(weights)


# ------------------------------------------------------------------ P-2 thresholds


def test_classification_gap_is_rejected() -> None:
    bands = [dict(b) for b in VALID_THRESHOLDS["bands"]]
    bands[1]["max_score"] = 70
    with pytest.raises(ValidationError):
        ClassificationThresholds.model_validate({"bands": bands})


def test_classification_overlap_is_rejected() -> None:
    bands = [dict(b) for b in VALID_THRESHOLDS["bands"]]
    bands[1]["max_score"] = 72
    with pytest.raises(ValidationError):
        ClassificationThresholds.model_validate({"bands": bands})


def test_classification_not_covering_zero_to_hundred_is_rejected() -> None:
    bands = [dict(b) for b in VALID_THRESHOLDS["bands"]]
    bands[3]["min_score"] = 1
    with pytest.raises(ValidationError):
        ClassificationThresholds.model_validate({"bands": bands})


def test_classification_band_outside_zero_to_hundred_is_rejected() -> None:
    bands = [dict(b) for b in VALID_THRESHOLDS["bands"]]
    bands[0]["max_score"] = 101
    with pytest.raises(ValidationError):
        ClassificationThresholds.model_validate({"bands": bands})


def test_insufficient_evidence_may_not_hold_a_score_band() -> None:
    """C-4: it is reachable only through the critical-unknown cap."""
    bands = [dict(b) for b in VALID_THRESHOLDS["bands"]]
    bands[2]["classification"] = "INSUFFICIENT_EVIDENCE"
    with pytest.raises(ValidationError):
        ClassificationThresholds.model_validate({"bands": bands})


# ------------------------------------------------------------------- P-3 seniority


def test_seniority_point_set_must_be_exact() -> None:
    bands = [dict(b) for b in VALID_SENIORITY["bands"]]
    bands[2]["points"] = 8
    with pytest.raises(ValidationError):
        SeniorityBands.model_validate({"bands": bands})


def test_seniority_bands_must_descend() -> None:
    bands = [dict(b) for b in VALID_SENIORITY["bands"]]
    bands.reverse()
    with pytest.raises(ValidationError):
        SeniorityBands.model_validate({"bands": bands})


# ---------------------------------------------------------------- P-4 compensation


def _bands() -> list[dict[str, Any]]:
    return [
        {
            "classification": "BELOW_80K",
            "min_usd": None,
            "max_usd": 80000,
            "hard_blocker": True,
            "points": 0,
            "report_note": "below floor",
        },
        {
            "classification": "FALLBACK_80K_TO_85K",
            "min_usd": 80000,
            "max_usd": 86000,
            "hard_blocker": False,
            "points": 5,
            "report_note": "fallback",
        },
        {
            "classification": "BELOW_PREFERRED_REVIEW",
            "min_usd": 86000,
            "max_usd": 90000,
            "hard_blocker": False,
            "points": 7,
            "report_note": "below preferred",
        },
        {
            "classification": "TARGET_90K_PLUS",
            "min_usd": 90000,
            "max_usd": None,
            "hard_blocker": False,
            "points": 10,
            "report_note": "target",
        },
    ]


def _compensation(bands: list[dict[str, Any]], **overrides: Any) -> CompensationConfig:
    payload: dict[str, Any] = {
        "currency": "USD",
        "bands": bands,
        "contract_points": 0,
        "unknown_points": 0,
        "contract_handling": "never annualize",
        "unknown_handling": "never reject on absence alone",
        "salary_targets": dict(VALID_SALARY_TARGETS),
        "market_reference": VALID_MARKET_REFERENCE,
        "regional_price_parity": VALID_RPP,
    }
    payload.update(overrides)
    return CompensationConfig.model_validate(payload)


def test_contiguous_bands_are_accepted() -> None:
    assert len(_compensation(_bands()).bands) == 4


def test_band_gap_is_rejected() -> None:
    bands = _bands()
    bands[2]["min_usd"] = 87000
    with pytest.raises(ValidationError):
        _compensation(bands)


def test_band_overlap_is_rejected() -> None:
    bands = _bands()
    bands[2]["min_usd"] = 85000
    with pytest.raises(ValidationError):
        _compensation(bands)


def test_open_lower_bound_is_required() -> None:
    bands = _bands()
    bands[0]["min_usd"] = 1
    with pytest.raises(ValidationError):
        _compensation(bands)


def test_compensation_points_must_not_decrease_as_the_band_rises() -> None:
    bands = _bands()
    bands[2]["points"] = 3
    with pytest.raises(ValidationError):
        _compensation(bands)


def test_below_80k_must_be_zero_points_and_blocking() -> None:
    bands = _bands()
    bands[0]["points"] = 4
    with pytest.raises(ValidationError):
        _compensation(bands)


def test_contract_and_unknown_must_score_zero() -> None:
    with pytest.raises(ValidationError):
        _compensation(_bands(), contract_points=4)
    with pytest.raises(ValidationError):
        _compensation(_bands(), unknown_points=2)


# ------------------------------------------------------------------ P-5 senior scope


def test_senior_scope_requires_exactly_seven_categories() -> None:
    rule = dict(VALID_SENIOR_SCOPE)
    rule["unsupported_requirement_categories"] = list(
        VALID_SENIOR_SCOPE["unsupported_requirement_categories"]
    )[:-1]
    with pytest.raises(ValidationError):
        SeniorScopeRule.model_validate(rule)


def test_senior_scope_minimum_below_two_is_rejected() -> None:
    rule = dict(VALID_SENIOR_SCOPE)
    rule["minimum_unsupported_requirements"] = 1
    with pytest.raises(ValidationError):
        SeniorScopeRule.model_validate(rule)


def test_senior_title_alone_cannot_be_configured_to_block() -> None:
    rule = dict(VALID_SENIOR_SCOPE)
    rule["requires_explicit_senior_scope"] = False
    with pytest.raises(ValidationError):
        SeniorScopeRule.model_validate(rule)


def test_senior_scope_requires_title_tokens() -> None:
    rule = dict(VALID_SENIOR_SCOPE)
    rule["senior_title_tokens"] = []
    with pytest.raises(ValidationError):
        SeniorScopeRule.model_validate(rule)


# --------------------------------------------------------------- P-6 report display


def test_report_order_must_be_the_approved_sequence() -> None:
    policy = {"order": list(VALID_REPORT_DISPLAY["order"]), "score_never_headline": True}
    policy["order"][0], policy["order"][4] = policy["order"][4], policy["order"][0]
    with pytest.raises(ValidationError):
        ReportDisplayPolicy.model_validate(policy)


def test_score_never_headline_must_be_true() -> None:
    policy = {"order": list(VALID_REPORT_DISPLAY["order"]), "score_never_headline": False}
    with pytest.raises(ValidationError):
        ReportDisplayPolicy.model_validate(policy)


# ------------------------------------------------------------------------ blockers


def _blocker_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "degree_equivalency_phrases": ["or equivalent experience"],
        "blockers": [{"code": c.value, "enabled": True} for c in BlockerCode],
        "senior_scope": VALID_SENIOR_SCOPE,
    }
    payload.update(overrides)
    return payload


def test_incomplete_blocker_set_is_rejected() -> None:
    codes = list(BlockerCode)[:-1]
    with pytest.raises(ValidationError):
        BlockerConfig.model_validate(
            _blocker_payload(blockers=[{"code": c.value, "enabled": True} for c in codes])
        )


def test_empty_phrase_list_is_rejected() -> None:
    with pytest.raises(ValidationError):
        BlockerConfig.model_validate(_blocker_payload(degree_equivalency_phrases=[]))


# ----------------------------------------------------------------------- risk flags


def test_duplicate_risk_flag_is_rejected() -> None:
    rules = [{"flag": f.value, "enabled": True} for f in RiskFlag]
    rules.append({"flag": RiskFlag.PAYMENT_REQUEST.value, "enabled": True})
    with pytest.raises(ValidationError):
        RiskFlagConfig.model_validate({"flags": rules})


def test_incomplete_risk_flag_set_is_rejected() -> None:
    rules = [{"flag": f.value, "enabled": True} for f in RiskFlag][:-1]
    with pytest.raises(ValidationError):
        RiskFlagConfig.model_validate({"flags": rules})


# =============================================================== A-5 allocation policy


def test_valid_allocation_policy_is_accepted() -> None:
    policy = TechnologyAllocationPolicy.model_validate(dict(VALID_ALLOCATION))
    assert policy.allocation == "required_only_conservative"


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("dimension", "role_family_relevance", "allocation dimension"),
        ("zero_required_slots_points", 3, "zero required slots"),
        ("preferred_in_numerator", True, "never enter the numerator"),
        ("preferred_in_denominator", True, "never enter the numerator"),
        ("unrecognized_required_term_credit", 0.5, "zero credit"),
        ("unrecognized_required_term_stays_in_denominator", False, "in the denominator"),
        ("prose_token_scanning", True, "never token-scanned"),
    ],
)
def test_allocation_policy_rejects_each_departure(
    field: str, value: Any, match: str
) -> None:
    """Each A-5 rule is enforced on its own, with its own reason."""
    payload = dict(VALID_ALLOCATION)
    payload[field] = value
    with pytest.raises(ValidationError, match=match):
        TechnologyAllocationPolicy.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("allocation", "required_weighted_balanced"),
        ("numerator_source", "raw_listing_prose"),
        ("rounding", "half_up"),
    ],
)
def test_allocation_policy_rejects_an_unapproved_literal(field: str, value: str) -> None:
    payload = dict(VALID_ALLOCATION)
    payload[field] = value
    with pytest.raises(ValidationError):
        TechnologyAllocationPolicy.model_validate(payload)


# ============================================================ A-6 canonical identifiers


@pytest.mark.parametrize("identifier", ["react", "React", "rest-apis", "_REACT", "2REACT"])
def test_canonical_identifier_shape_is_enforced(identifier: str) -> None:
    with pytest.raises(ValidationError, match="uppercase-snake"):
        CanonicalTechnology.model_validate({"id": identifier, "display_name": "React"})


def test_canonical_identifier_requires_a_display_name() -> None:
    with pytest.raises(ValidationError, match="display name"):
        CanonicalTechnology.model_validate({"id": "REACT", "display_name": "  "})


def test_uppercase_snake_identifier_with_digits_is_accepted() -> None:
    """BM25 must be a legal identifier."""
    assert CanonicalTechnology.model_validate({"id": "BM25", "display_name": "BM25"}).id == (
        "BM25"
    )


# ================================================================ A-6 alias families


def test_valid_alias_family_is_accepted() -> None:
    family = AliasFamily.model_validate(dict(VALID_ALIAS_FAMILY))
    assert family.variants == ("react.js", "reactjs")


def test_alias_family_requires_an_approval_date() -> None:
    payload = dict(VALID_ALIAS_FAMILY)
    payload["approval_date"] = "   "
    with pytest.raises(ValidationError, match="approval date"):
        AliasFamily.model_validate(payload)


def test_alias_family_requires_a_defense_statement() -> None:
    payload = dict(VALID_ALIAS_FAMILY)
    payload["defense"] = ""
    with pytest.raises(ValidationError, match="defense statement"):
        AliasFamily.model_validate(payload)


def test_alias_family_requires_variants() -> None:
    payload = dict(VALID_ALIAS_FAMILY)
    payload["variants"] = []
    with pytest.raises(ValidationError, match="requires variants"):
        AliasFamily.model_validate(payload)


def test_alias_family_rejects_a_duplicate_variant() -> None:
    payload = dict(VALID_ALIAS_FAMILY)
    payload["variants"] = ["react.js", "react.js"]
    with pytest.raises(ValidationError, match="duplicate variant"):
        AliasFamily.model_validate(payload)


@pytest.mark.parametrize(
    "variant", ["React.js", "REACTJS", " react.js", "react.js ", "react  js"]
)
def test_alias_variant_keys_must_already_be_normalized(variant: str) -> None:
    """A-6: the four steps are NFC, casefold, whitespace collapse, and trim."""
    payload = dict(VALID_ALIAS_FAMILY)
    payload["variants"] = [variant]
    with pytest.raises(ValidationError, match="normalized lookup key"):
        AliasFamily.model_validate(payload)


def test_an_already_normalized_multiword_variant_is_accepted() -> None:
    payload = dict(VALID_ALIAS_FAMILY)
    payload["canonical_id"] = "REST_APIS"
    payload["variants"] = ["restful apis"]
    assert AliasFamily.model_validate(payload).variants == ("restful apis",)


@pytest.mark.parametrize("variant", ["js", "ts"])
def test_bare_two_letter_variant_is_rejected(variant: str) -> None:
    """TS also denotes Top Secret; JS/TS is a compound requirement, not an alias."""
    payload = dict(VALID_ALIAS_FAMILY)
    payload["variants"] = [variant]
    with pytest.raises(ValidationError, match="two-letter"):
        AliasFamily.model_validate(payload)


@pytest.mark.parametrize(
    "variant",
    [
        "crontab",
        "openssh",
        "js/ts",
        "javascript/typescript",
        "react native",
        "ubuntu",
        "vector database",
    ],
)
def test_deferred_alias_variant_is_rejected(variant: str) -> None:
    """A-6: every deferred variant is unusable, including in a new family."""
    payload = dict(VALID_ALIAS_FAMILY)
    payload["variants"] = [variant]
    with pytest.raises(ValidationError, match="explicitly deferred"):
        AliasFamily.model_validate(payload)


def test_alias_family_identifier_shape_is_enforced() -> None:
    payload = dict(VALID_ALIAS_FAMILY)
    payload["canonical_id"] = "react"
    with pytest.raises(ValidationError, match="uppercase-snake"):
        AliasFamily.model_validate(payload)


# ============================================================ A-6 normalization policy


def test_valid_normalization_policy_is_accepted() -> None:
    policy = TechnologyNormalizationPolicy.model_validate(_normalization())
    assert len(policy.alias_families) == APPROVED_ALIAS_FAMILY_COUNT == 9
    assert sum(len(f.variants) for f in policy.alias_families) == (
        APPROVED_ALIAS_VARIANT_COUNT
    )


@pytest.mark.parametrize(
    "steps",
    [
        ["casefold", "collapse_whitespace", "trim"],
        ["nfc", "casefold", "collapse_whitespace", "trim", "strip_punctuation"],
        ["nfc", "casefold", "strip_version", "trim"],
        ["nfc", "casefold", "expand_acronyms", "trim"],
        ["casefold", "nfc", "collapse_whitespace", "trim"],
    ],
)
def test_normalization_steps_must_be_exactly_the_four_approved_steps(
    steps: list[str],
) -> None:
    with pytest.raises(ValidationError, match="normalization steps"):
        TechnologyNormalizationPolicy.model_validate(_normalization(normalization_steps=steps))


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("whole_phrase_only", False, "whole-phrase only"),
        ("unknown_alias_auto_match", True, "never auto-match"),
        ("bare_two_letter_aliases_allowed", True, "two-letter"),
        ("persistent_review_queue", True, "persistent review queue"),
    ],
)
def test_normalization_policy_rejects_each_departure(
    field: str, value: Any, match: str
) -> None:
    with pytest.raises(ValidationError, match=match):
        TechnologyNormalizationPolicy.model_validate(_normalization(**{field: value}))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("alias_direction", "bidirectional"),
        ("candidate_side_compound_parsing", "enabled"),
        ("unknown_term_handling", "auto_match"),
    ],
)
def test_normalization_policy_rejects_an_unapproved_literal(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        TechnologyNormalizationPolicy.model_validate(_normalization(**{field: value}))


def test_duplicate_canonical_identifier_in_the_registry_is_rejected() -> None:
    registry = [{"id": i, "display_name": d} for i, d in APPROVED_CANONICAL_TECHNOLOGIES]
    registry.append({"id": "REACT", "display_name": "React"})
    with pytest.raises(ValidationError, match="duplicate canonical identifier"):
        TechnologyNormalizationPolicy.model_validate(
            _normalization(canonical_technologies=registry)
        )


def test_each_canonical_identifier_has_exactly_one_display_name() -> None:
    """A second display name for the same identifier is a duplicate identifier."""
    registry = [{"id": i, "display_name": d} for i, d in APPROVED_CANONICAL_TECHNOLOGIES]
    registry.append({"id": "REACT", "display_name": "React.js"})
    with pytest.raises(ValidationError, match="duplicate canonical identifier"):
        TechnologyNormalizationPolicy.model_validate(
            _normalization(canonical_technologies=registry)
        )


def test_alias_family_targeting_an_unregistered_identifier_is_rejected() -> None:
    families = [
        {
            "canonical_id": identifier,
            "approval_date": "2026-09-26",
            "defense": "same technology",
            "variants": list(variants),
        }
        for identifier, variants in APPROVED_ALIAS_FAMILIES
    ]
    families.append(
        {
            "canonical_id": "LANGCHAIN",
            "approval_date": "2026-09-26",
            "defense": "same technology",
            "variants": ["langchain framework"],
        }
    )
    with pytest.raises(ValidationError, match="no approved display name"):
        TechnologyNormalizationPolicy.model_validate(_normalization(alias_families=families))


def test_no_variant_may_map_to_two_canonical_identifiers() -> None:
    families = [
        {
            "canonical_id": identifier,
            "approval_date": "2026-09-26",
            "defense": "same technology",
            "variants": list(variants),
        }
        for identifier, variants in APPROVED_ALIAS_FAMILIES
    ]
    families[1]["variants"] = [*families[1]["variants"], "reactjs"]
    with pytest.raises(ValidationError, match="maps to both"):
        TechnologyNormalizationPolicy.model_validate(_normalization(alias_families=families))


def test_duplicate_canonical_identifier_across_families_is_rejected() -> None:
    families = [
        {
            "canonical_id": identifier,
            "approval_date": "2026-09-26",
            "defense": "same technology",
            "variants": list(variants),
        }
        for identifier, variants in APPROVED_ALIAS_FAMILIES
    ]
    families.append(
        {
            "canonical_id": "REACT",
            "approval_date": "2026-09-26",
            "defense": "same technology",
            "variants": ["react framework"],
        }
    )
    with pytest.raises(ValidationError, match="duplicate canonical identifier"):
        TechnologyNormalizationPolicy.model_validate(_normalization(alias_families=families))


def test_dropping_an_approved_family_is_rejected() -> None:
    families = [
        {
            "canonical_id": identifier,
            "approval_date": "2026-09-26",
            "defense": "same technology",
            "variants": list(variants),
        }
        for identifier, variants in APPROVED_ALIAS_FAMILIES
    ][:-1]
    with pytest.raises(ValidationError, match="approved initial registry"):
        TechnologyNormalizationPolicy.model_validate(_normalization(alias_families=families))


def test_removing_a_deferred_variant_from_the_deferred_set_is_rejected() -> None:
    deferred = [v for v in VALID_NORMALIZATION["deferred_alias_variants"] if v != "crontab"]
    with pytest.raises(ValidationError, match="approved deferred set"):
        TechnologyNormalizationPolicy.model_validate(
            _normalization(deferred_alias_variants=deferred)
        )


def test_deferred_mappings_and_categories_must_be_recorded() -> None:
    with pytest.raises(ValidationError, match="deferred alias mappings"):
        TechnologyNormalizationPolicy.model_validate(
            _normalization(deferred_alias_mappings=[])
        )
    with pytest.raises(ValidationError, match="deferred alias categories"):
        TechnologyNormalizationPolicy.model_validate(
            _normalization(deferred_alias_categories=[])
        )


# ============================================================ A-7 required vs preferred


def test_valid_required_preferred_policy_is_accepted() -> None:
    policy = RequiredPreferredPolicy.model_validate(dict(VALID_REQUIRED_PREFERRED))
    assert policy.required_only_dimension_input is True


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("required_only_dimension_input", False, "only input"),
        ("preferred_raises_required_skill_gap", True, "never raise REQUIRED_SKILL_GAP"),
        ("preferred_evidence_map_required", False, "preferred-evidence map"),
        (
            "preferred_influences_human_next_action_wording_only",
            False,
            "Human next action wording",
        ),
        ("no_explicit_required_technologies_points", 4, "scores 0 in this"),
        ("any_of_slot_count", 2, "one any-of slot"),
        ("equivalent_may_introduce_new_technology", True, "never invents"),
        ("generic_wording_becomes_slot", True, "generic wording"),
        (
            "critical_unknown_when_structured_field_yields_no_technology",
            False,
            "critical unknown",
        ),
    ],
)
def test_required_preferred_policy_rejects_each_departure(
    field: str, value: Any, match: str
) -> None:
    payload = dict(VALID_REQUIRED_PREFERRED)
    payload[field] = value
    with pytest.raises(ValidationError, match=match):
        RequiredPreferredPolicy.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("preferred_score_effect", "partial"),
        ("preferred_classification_effect", "partial"),
        ("preferred_recommendation_effect", "partial"),
        ("preferred_flag_effect", "partial"),
        ("compound_all_of_slot", "implemented"),
        ("preferred_extraction", "implemented"),
    ],
)
def test_required_preferred_policy_rejects_an_unapproved_literal(
    field: str, value: str
) -> None:
    payload = dict(VALID_REQUIRED_PREFERRED)
    payload[field] = value
    with pytest.raises(ValidationError):
        RequiredPreferredPolicy.model_validate(payload)


# ============================================================= gate cannot be widened


def test_a_resolved_key_cannot_be_smuggled_back_into_the_gate() -> None:
    """The three resolved keys are no longer gate keys; readdition is rejected."""
    gate = _unresolved_policy()
    gate["technology_base_credit_allocation"] = UNRESOLVED
    with pytest.raises(ValidationError):
        _scoring(unresolved_policy=gate)


def test_the_gate_is_exactly_eleven_keys_in_the_approved_order() -> None:
    """Exact named tuple, never a count. Five policy keys plus six allocation-rule keys."""
    assert REQUIRED_UNRESOLVED_POLICY_KEYS == (
        "seniority_band_selection_precedence",
        "compensation_range_selection_rule",
        "critical_unknown_detection_rule",
        "score_rounding_rule",
        "report_and_cli_score_display_scope",
        "role_family_allocation_rule",
        "responsibility_evidence_allocation_rule",
        "location_remote_relocation_allocation_rule",
        "employment_type_allocation_rule",
        "growth_learning_allocation_rule",
        "employer_listing_validation_allocation_rule",
    )
    assert _scoring().unresolved_keys() == REQUIRED_UNRESOLVED_POLICY_KEYS


def test_every_allocation_key_names_a_weighted_dimension() -> None:
    """An allocation key that governs no dimension would track nothing."""
    from vetted.core.config.schema import ALLOCATION_RULE_DIMENSIONS, ALLOCATION_RULE_KEYS

    assert set(ALLOCATION_RULE_DIMENSIONS) == set(ALLOCATION_RULE_KEYS)
    assert set(ALLOCATION_RULE_KEYS) <= set(REQUIRED_UNRESOLVED_POLICY_KEYS)
    weights = _scoring().weights
    for key, dimension in ALLOCATION_RULE_DIMENSIONS.items():
        assert dimension in weights, f"{key} names {dimension!r}, which is not weighted"
    assert sum(weights[d] for d in ALLOCATION_RULE_DIMENSIONS.values()) == 55


def test_the_unevaluated_ceiling_is_eighty_two() -> None:
    """C-2 keeps an unevaluated dimension in the denominator.

    Responsibility (15) and growth (3) have no deterministic input, so while they stay
    unevaluated the highest achievable total is 82, and the P-2 bands cannot be applied.
    """
    weights = _scoring().weights
    unevaluable = (
        weights["responsibility_and_project_evidence_alignment"]
        + weights["growth_learning_relevance"]
    )
    assert unevaluable == 18
    assert sum(weights.values()) - unevaluable == 82


# ======================================================== technology categories


def _categories(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "substitution_credit": dict(VALID_CATEGORIES["substitution_credit"]),
        "categories": [dict(c) for c in VALID_CATEGORIES["categories"]],
    }
    payload.update(overrides)
    return payload


def test_valid_category_table_is_accepted() -> None:
    table = TechnologyCategories.model_validate(_categories())
    assert table.category_for("salesforce").name == "CRM_TICKETING"
    assert table.category_for("rust").substitutable is False
    assert table.category_for("nothing") is None


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("direct", 0.9, "reference and must equal 1.0"),
        ("none", 0.1, "must earn exactly 0.0"),
        ("substitute", 1.0, "never worth the requested tool"),
        ("substitute", 0.0, "worth something"),
        ("substitute", 1.5, "never worth the requested tool"),
    ],
)
def test_substitution_credit_bounds(field: str, value: float, match: str) -> None:
    """A peer tool is worth something, and never worth the requested tool."""
    credit = dict(VALID_CATEGORIES["substitution_credit"])
    credit[field] = value
    with pytest.raises(ValidationError, match=match):
        TechnologyCategories.model_validate(_categories(substitution_credit=credit))


def test_a_technology_may_not_sit_in_two_categories() -> None:
    """Otherwise substitutability is ambiguous."""
    categories = [dict(c) for c in VALID_CATEGORIES["categories"]]
    categories[1]["members"] = [*categories[1]["members"], "Salesforce"]
    with pytest.raises(ValidationError, match="belongs to one category"):
        TechnologyCategories.model_validate(_categories(categories=categories))


def test_a_category_needs_two_members_and_a_note() -> None:
    categories = [dict(c) for c in VALID_CATEGORIES["categories"]]
    categories[0]["members"] = ["Salesforce"]
    with pytest.raises(ValidationError, match="at least two members"):
        TechnologyCategories.model_validate(_categories(categories=categories))
    categories = [dict(c) for c in VALID_CATEGORIES["categories"]]
    categories[0]["note"] = "  "
    with pytest.raises(ValidationError, match="requires a note"):
        TechnologyCategories.model_validate(_categories(categories=categories))


# ============================================================== salary targets


def test_salary_targets_must_ascend() -> None:
    payload = dict(VALID_SALARY_TARGETS)
    payload["market_target_usd"] = 80000
    with pytest.raises(ValidationError, match="must ascend"):
        SalaryTargets.model_validate(payload)


def test_a_market_figure_requires_a_source_and_date() -> None:
    """An uncited salary figure is a guess, and a guess about pay is worse than none."""
    for field in ("as_of", "source", "note"):
        row = dict(VALID_MARKET_REFERENCE["rows"][0])
        row[field] = "   "
        with pytest.raises(ValidationError, match="required for a market figure"):
            MarketReference.model_validate({"status": "PROVISIONAL", "rows": [row]})


def test_remote_roles_may_not_be_cost_of_living_adjusted() -> None:
    """The candidate spends at home prices, so adjusting down would penalise best offers."""
    payload = dict(VALID_RPP)
    payload["apply_only_on_relocation"] = False
    with pytest.raises(ValidationError, match="must not be cost-of-living adjusted"):
        RegionalPriceParity.model_validate(payload)


def test_relocation_ratio_declines_an_unlisted_state() -> None:
    """No interpolated guesses: an unlisted state yields no adjustment."""
    rpp = RegionalPriceParity.model_validate(dict(VALID_RPP))
    assert rpp.relocation_ratio("TX") is None
    assert rpp.relocation_ratio("CA") == pytest.approx(96.3 / 110.7)


def test_the_candidate_state_must_have_a_parity() -> None:
    payload = dict(VALID_RPP)
    payload["states"] = {"CA": 110.7}
    with pytest.raises(ValidationError, match="candidate state"):
        RegionalPriceParity.model_validate(payload)
