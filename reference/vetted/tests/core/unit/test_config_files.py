"""Tests against the shipped configuration in `config/`.

Structural validation must pass. Readiness validation must fail on exactly the five approved
unresolved keys, and on nothing else. A-5 through A-7 removed three keys from that gate on
2026-09-26 and replaced them with typed policy blocks; no behaviour was added.
"""

from pathlib import Path

import pytest

from vetted.core.config.loader import load_assessment_config, load_ready_assessment_config
from vetted.core.config.schema import (
    APPROVED_ALIAS_FAMILIES,
    APPROVED_ALIAS_FAMILY_COUNT,
    APPROVED_ALIAS_VARIANT_COUNT,
    APPROVED_CANONICAL_TECHNOLOGIES,
    APPROVED_NORMALIZATION_STEPS,
    APPROVED_REPORT_ORDER,
    DEFERRED_ALIAS_VARIANTS,
    REQUIRED_UNRESOLVED_POLICY_KEYS,
    AssessmentPolicyUnresolvedError,
)
from vetted.core.enums import (
    BlockerCode,
    EvidenceTier,
    MatchClassification,
    PolicyStatus,
    RiskFlag,
    SalaryCompatibility,
)

APPROVED_PHRASES = (
    "or equivalent experience",
    "or equivalent practical experience",
    "or equivalent professional experience",
    "or equivalent work experience",
    "or related experience",
    "equivalent combination of education and experience",
    "education or equivalent experience",
    "degree preferred",
    "bachelor's preferred",
    "or demonstrable experience",
)


def test_shipped_configuration_parses_structurally(config_dir: Path) -> None:
    """Stage 1 must succeed so import, lint, type check, test, and CLI help all work."""
    config = load_assessment_config(config_dir)
    assert sum(config.scoring.weights.values()) == 100


def test_shipped_configuration_is_not_ready(config_dir: Path) -> None:
    """Stage 2 must fail while the approved policy gate remains unresolved."""
    with pytest.raises(AssessmentPolicyUnresolvedError) as excinfo:
        load_ready_assessment_config(config_dir)
    assert excinfo.value.unresolved_keys == REQUIRED_UNRESOLVED_POLICY_KEYS
    for key in REQUIRED_UNRESOLVED_POLICY_KEYS:
        assert key in str(excinfo.value)


def test_unresolved_key_set_is_exact(config_dir: Path) -> None:
    """The exact named tuple in the approved order. Never merely a count."""
    assert load_assessment_config(config_dir).unresolved_keys() == (
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


def test_every_unruled_dimension_has_a_gate_key(config_dir: Path) -> None:
    """The six dimensions holding 55 points are now tracked, not invisible."""
    from vetted.core.config.schema import ALLOCATION_RULE_DIMENSIONS, ALLOCATION_RULE_KEYS

    config = load_assessment_config(config_dir)
    gate = config.unresolved_keys()
    for key in ALLOCATION_RULE_KEYS:
        assert key in gate
    weights = config.scoring.weights
    for key, dimension in ALLOCATION_RULE_DIMENSIONS.items():
        assert dimension in weights, f"{key} names a dimension that is not weighted"
    assert sum(weights[d] for d in ALLOCATION_RULE_DIMENSIONS.values()) == 55


def test_the_sentinel_is_the_only_value_in_the_gate(config_dir: Path) -> None:
    """Shipped configuration must carry no released or annotated gate value."""
    gate = load_assessment_config(config_dir).scoring.unresolved_policy
    assert set(gate.values()) == {"UNRESOLVED"}


def test_resolved_keys_are_absent_from_the_unresolved_gate(config_dir: Path) -> None:
    """A-5 through A-7: the three resolved keys no longer gate readiness."""
    gate = load_assessment_config(config_dir).scoring.unresolved_policy
    for key in (
        "technology_base_credit_allocation",
        "technology_matching_normalization",
        "required_vs_preferred_technology_handling",
    ):
        assert key not in gate


def test_seniority_dimension_uses_the_approved_name(config_dir: Path) -> None:
    """D-4."""
    weights = load_assessment_config(config_dir).scoring.weights
    assert weights["seniority_and_documented_evidence_compatibility"] == 15
    assert "seniority_years" not in weights


def test_bands_tile_the_range_without_gap_or_overlap(config_dir: Path) -> None:
    """D-3."""
    bands = load_assessment_config(config_dir).compensation.bands
    ordered = sorted(bands, key=lambda b: (b.min_usd is not None, b.min_usd or 0))
    assert ordered[0].min_usd is None
    assert ordered[-1].max_usd is None
    for lower, upper in zip(ordered, ordered[1:], strict=False):
        assert lower.max_usd == upper.min_usd


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (79_999, SalaryCompatibility.BELOW_80K),
        (80_000, SalaryCompatibility.FALLBACK_80K_TO_85K),
        (85_999, SalaryCompatibility.FALLBACK_80K_TO_85K),
        (86_000, SalaryCompatibility.BELOW_PREFERRED_REVIEW),
        (89_999, SalaryCompatibility.BELOW_PREFERRED_REVIEW),
        (90_000, SalaryCompatibility.TARGET_90K_PLUS),
        (250_000, SalaryCompatibility.TARGET_90K_PLUS),
    ],
)
def test_every_boundary_amount_falls_in_exactly_one_band(
    config_dir: Path, amount: int, expected: SalaryCompatibility
) -> None:
    """Computed in the test, not in the package: Phase 1A implements no band lookup."""
    bands = load_assessment_config(config_dir).compensation.bands
    matched = [
        band
        for band in bands
        if (band.min_usd is None or amount >= band.min_usd)
        and (band.max_usd is None or amount < band.max_usd)
    ]
    assert len(matched) == 1
    assert matched[0].classification is expected


def test_no_compensation_band_is_a_hard_blocker(config_dir: Path) -> None:
    """Owner decision 2026-09-26: the salary floor is soft.

    A few thousand under a stated minimum can still be a good opportunity, and that is a
    judgement for a human. A low salary scores zero and is reported with its shortfall; it is
    never an automatic rejection.
    """
    config = load_assessment_config(config_dir)
    assert not [band for band in config.compensation.bands if band.hard_blocker]
    disabled = {
        rule.code for rule in config.blockers.blockers if not rule.enabled
    }
    assert BlockerCode.EXPLICIT_BASE_SALARY_BELOW_80K in disabled


def test_the_salary_blocker_code_still_exists(config_dir: Path) -> None:
    """The blocker set is parity-locked to PROJECT_GUARDRAILS.md, so the code stays defined."""
    codes = {rule.code for rule in load_assessment_config(config_dir).blockers.blockers}
    assert codes == set(BlockerCode)
    assert SalaryCompatibility.BELOW_80K in {
        band.classification for band in load_assessment_config(config_dir).compensation.bands
    }


def test_salary_targets_are_the_approved_triple(config_dir: Path) -> None:
    """70k hard floor, 85k soft minimum, 120k market target. None of them blocks."""
    targets = load_assessment_config(config_dir).compensation.salary_targets
    assert (targets.hard_floor_usd, targets.soft_minimum_usd, targets.market_target_usd) == (
        70_000,
        85_000,
        120_000,
    )
    assert targets.status is PolicyStatus.PROVISIONAL


def test_every_market_figure_is_cited(config_dir: Path) -> None:
    for row in load_assessment_config(config_dir).compensation.market_reference.rows:
        assert row.source.startswith("https://")
        assert row.as_of
        assert row.value > 0


def test_cost_of_living_applies_only_on_relocation(config_dir: Path) -> None:
    """Remote work at Georgia prices is an advantage, not something to discount."""
    rpp = load_assessment_config(config_dir).compensation.regional_price_parity
    assert rpp.apply_only_on_relocation is True
    assert rpp.candidate_state == "GA"
    assert rpp.relocation_ratio("CA") < 1.0
    assert rpp.relocation_ratio("NY") < 1.0
    assert rpp.relocation_ratio("NC") > 1.0, "a cheaper state must read as upside"
    assert rpp.relocation_ratio("CO") is None, "an unverified state gets no estimate"


def test_the_category_table_encodes_the_substitutability_rule(config_dir: Path) -> None:
    """A CRM is a CRM. A Rust job needs Rust."""
    table = load_assessment_config(config_dir).scoring.technology_categories
    assert table.category_for("salesforce").substitutable is True
    assert table.category_for("freshdesk").substitutable is True
    assert table.category_for("rust").substitutable is False
    assert table.category_for("python").substitutable is False
    assert table.substitution_credit.substitute == 0.50


def test_below_preferred_review_note_states_both_boundaries(config_dir: Path) -> None:
    """A-2 requires the report to state the position relative to both figures."""
    bands = load_assessment_config(config_dir).compensation.bands
    note = next(
        band.report_note
        for band in bands
        if band.classification is SalaryCompatibility.BELOW_PREFERRED_REVIEW
    )
    assert "90,000" in note
    assert "80,000" in note


def test_degree_equivalency_phrases_are_the_approved_list(config_dir: Path) -> None:
    """D-8."""
    phrases = load_assessment_config(config_dir).blockers.degree_equivalency_phrases
    assert phrases == APPROVED_PHRASES


def test_blocker_set_is_complete_and_expected(config_dir: Path) -> None:
    """D-5, D-6, D-10 shape this set."""
    codes = {rule.code for rule in load_assessment_config(config_dir).blockers.blockers}
    assert codes == set(BlockerCode)
    assert len(codes) == 7


def test_risk_flag_registry_is_complete(config_dir: Path) -> None:
    flags = {rule.flag for rule in load_assessment_config(config_dir).risk_flags.flags}
    assert flags == set(RiskFlag)
    assert len(flags) == 24


def test_blockers_config_declares_no_salary_override(repo_root: Path) -> None:
    """D-10: the override is deferred, so no key may hint at one."""
    text = (repo_root / "config" / "policy" / "blockers.yaml").read_text(encoding="utf-8")
    keys = [
        line.split(":", 1)[0].strip().lstrip("- ")
        for line in text.splitlines()
        if ":" in line and not line.strip().startswith("#")
    ]
    assert not [key for key in keys if "override" in key.lower()]


def test_risk_flag_config_declares_no_detection_patterns(repo_root: Path) -> None:
    """Detection patterns are Phase 3 work and must be absent."""
    text = (repo_root / "config" / "policy" / "risk_flags.yaml").read_text(encoding="utf-8")
    directives = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("#")
    )
    assert "pattern" not in directives.lower()


def test_missing_config_file_is_reported_clearly(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_assessment_config(tmp_path)


# =========================================================================== P-1


def test_evidence_tier_multipliers_are_the_approved_values(config_dir: Path) -> None:
    """P-1."""
    weights = load_assessment_config(config_dir).scoring.evidence_tier_weighting
    assert weights.TIER_1_VERIFIED_SKILL == 1.00
    assert weights.TIER_2_PROJECT_EVIDENCE == 0.70
    assert weights.TIER_3_EMPLOYMENT_EVIDENCE == 0.90
    assert weights.TIER_4_TRAINING == 0.30


def test_every_evidence_tier_has_a_multiplier(config_dir: Path) -> None:
    weights = load_assessment_config(config_dir).scoring.evidence_tier_weighting
    for tier in EvidenceTier:
        assert getattr(weights, tier.value) > 0


def test_tier_3_outranks_tier_2(config_dir: Path) -> None:
    """E-8: tier ordinal does not imply weight order."""
    weights = load_assessment_config(config_dir).scoring.evidence_tier_weighting
    assert weights.TIER_3_EMPLOYMENT_EVIDENCE > weights.TIER_2_PROJECT_EVIDENCE


def test_tier_1_is_the_reference_multiplier(config_dir: Path) -> None:
    weights = load_assessment_config(config_dir).scoring.evidence_tier_weighting
    values = [getattr(weights, tier.value) for tier in EvidenceTier]
    assert weights.TIER_1_VERIFIED_SKILL == 1.00 == max(values)


def test_evidence_tier_cap_is_the_skill_dimension_weight(config_dir: Path) -> None:
    """E-1: multipliers are capped at verified_technical_skill_alignment."""
    config = load_assessment_config(config_dir)
    assert config.evidence_tier_cap_points() == 20
    assert config.evidence_tier_cap_points() == (
        config.scoring.weights["verified_technical_skill_alignment"]
    )


# =========================================================================== P-2


def test_classification_bands_are_the_approved_values(config_dir: Path) -> None:
    """P-2."""
    bands = load_assessment_config(config_dir).scoring.match_classification_thresholds.bands
    actual = {band.classification: (band.min_score, band.max_score) for band in bands}
    assert actual == {
        MatchClassification.STRONG_MATCH: (72, 100),
        MatchClassification.PLAUSIBLE_MATCH: (58, 71),
        MatchClassification.STRETCH: (42, 57),
        MatchClassification.AVOID: (0, 41),
    }


def test_classification_bands_tile_zero_to_one_hundred(config_dir: Path) -> None:
    bands = load_assessment_config(config_dir).scoring.match_classification_thresholds.bands
    ordered = sorted(bands, key=lambda b: b.min_score)
    assert ordered[0].min_score == 0
    assert ordered[-1].max_score == 100
    for lower, upper in zip(ordered, ordered[1:], strict=False):
        assert lower.max_score + 1 == upper.min_score


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, MatchClassification.AVOID),
        (41, MatchClassification.AVOID),
        (42, MatchClassification.STRETCH),
        (57, MatchClassification.STRETCH),
        (58, MatchClassification.PLAUSIBLE_MATCH),
        (71, MatchClassification.PLAUSIBLE_MATCH),
        (72, MatchClassification.STRONG_MATCH),
        (100, MatchClassification.STRONG_MATCH),
    ],
)
def test_classification_boundary_scores_fall_in_exactly_one_band(
    config_dir: Path, score: int, expected: MatchClassification
) -> None:
    """Computed in the test: Phase 1A implements no classification lookup."""
    bands = load_assessment_config(config_dir).scoring.match_classification_thresholds.bands
    matched = [b for b in bands if b.min_score <= score <= b.max_score]
    assert len(matched) == 1
    assert matched[0].classification is expected


def test_insufficient_evidence_has_no_score_band(config_dir: Path) -> None:
    """C-4: reachable only through the critical-unknown cap."""
    bands = load_assessment_config(config_dir).scoring.match_classification_thresholds.bands
    assert MatchClassification.INSUFFICIENT_EVIDENCE not in {b.classification for b in bands}


# =========================================================================== P-3


def test_seniority_bands_are_the_approved_point_values(config_dir: Path) -> None:
    """P-3."""
    bands = load_assessment_config(config_dir).scoring.seniority_bands.bands
    assert [band.points for band in bands] == [15, 11, 7, 3, 0]
    assert all(band.description.strip() for band in bands)


def test_seniority_band_maximum_equals_dimension_weight(config_dir: Path) -> None:
    config = load_assessment_config(config_dir)
    top = max(band.points for band in config.scoring.seniority_bands.bands)
    assert top == config.scoring.weights["seniority_and_documented_evidence_compatibility"] == 15


# =========================================================================== P-4


def test_compensation_points_are_the_approved_values(config_dir: Path) -> None:
    """P-4."""
    config = load_assessment_config(config_dir)
    points = {band.classification: band.points for band in config.compensation.bands}
    assert points == {
        SalaryCompatibility.TARGET_90K_PLUS: 10,
        SalaryCompatibility.BELOW_PREFERRED_REVIEW: 7,
        SalaryCompatibility.FALLBACK_80K_TO_85K: 5,
        SalaryCompatibility.BELOW_80K: 0,
    }
    assert config.compensation.contract_points == 0
    assert config.compensation.unknown_points == 0


def test_compensation_points_are_non_decreasing_as_the_band_rises(config_dir: Path) -> None:
    bands = load_assessment_config(config_dir).compensation.bands
    ordered = sorted(bands, key=lambda b: (b.min_usd is not None, b.min_usd or 0))
    points = [band.points for band in ordered]
    assert points == sorted(points)


def test_compensation_maximum_equals_dimension_weight(config_dir: Path) -> None:
    config = load_assessment_config(config_dir)
    top = max(band.points for band in config.compensation.bands)
    assert top == config.scoring.weights["compensation_compatibility"] == 10


# =========================================================================== P-5


def test_senior_scope_rule_requires_two_unsupported_requirements(config_dir: Path) -> None:
    """P-5: a senior title alone is never an automatic hard blocker."""
    rule = load_assessment_config(config_dir).blockers.senior_scope
    assert rule.requires_explicit_senior_scope is True
    assert rule.minimum_unsupported_requirements == 2
    assert len(rule.unsupported_requirement_categories) == 7
    assert "Senior" in rule.senior_title_tokens


def test_senior_scope_adds_no_blocker_code(config_dir: Path) -> None:
    codes = {rule.code for rule in load_assessment_config(config_dir).blockers.blockers}
    assert codes == set(BlockerCode)
    assert len(codes) == 7


# =========================================================================== P-6


def test_report_display_order_is_the_approved_sequence(config_dir: Path) -> None:
    """P-6."""
    display = load_assessment_config(config_dir).scoring.report_display
    assert display.order == APPROVED_REPORT_ORDER
    assert display.score_never_headline is True


def test_score_appears_at_position_five(config_dir: Path) -> None:
    """C-5: the score is never a headline."""
    order = load_assessment_config(config_dir).scoring.report_display.order
    assert order.index("Match classification and score") == 4
    assert order[0] == "Recommendation"
    assert order[1] == "Hard blockers"


# ====================================================================== A-5 to A-7


def test_shipped_configuration_declares_the_three_resolved_policy_blocks(
    config_dir: Path,
) -> None:
    """The three decisions exist as typed configuration, not as sentinels."""
    scoring = load_assessment_config(config_dir).scoring
    assert scoring.technology_base_credit_allocation.allocation == (
        "required_only_conservative"
    )
    assert scoring.technology_matching_normalization.alias_direction == (
        "variant_to_canonical"
    )
    assert scoring.required_vs_preferred_technology_handling.preferred_score_effect == "none"


def test_shipped_allocation_policy_is_the_approved_a5_policy(config_dir: Path) -> None:
    """A-5: preferred technologies enter neither side; rounding stays deferred."""
    policy = load_assessment_config(config_dir).scoring.technology_base_credit_allocation
    assert policy.dimension == "verified_technical_skill_alignment"
    assert policy.zero_required_slots_points == 0
    assert policy.preferred_in_numerator is False
    assert policy.preferred_in_denominator is False
    assert policy.unrecognized_required_term_credit == 0.00
    assert policy.unrecognized_required_term_stays_in_denominator is True
    assert policy.numerator_source == "structured_technology_fields_only"
    assert policy.prose_token_scanning is False
    assert policy.rounding == "deferred_to_score_rounding_rule"


def test_shipped_normalization_steps_are_the_four_approved_steps(config_dir: Path) -> None:
    """A-6: no punctuation stripping, version stripping, or acronym expansion."""
    policy = load_assessment_config(config_dir).scoring.technology_matching_normalization
    assert policy.normalization_steps == APPROVED_NORMALIZATION_STEPS
    assert policy.normalization_steps == ("nfc", "casefold", "collapse_whitespace", "trim")
    assert policy.whole_phrase_only is True
    assert policy.unknown_alias_auto_match is False
    assert policy.bare_two_letter_aliases_allowed is False
    assert policy.persistent_review_queue is False
    assert policy.unknown_term_handling == "report_section_only"


def test_shipped_display_name_registry_matches_the_approved_set(config_dir: Path) -> None:
    """A-6: nine canonical identifiers, one display name each, in the approved order."""
    policy = load_assessment_config(config_dir).scoring.technology_matching_normalization
    documented = tuple((e.id, e.display_name) for e in policy.canonical_technologies)
    assert documented == APPROVED_CANONICAL_TECHNOLOGIES
    assert documented == (
        ("REACT", "React"),
        ("REST_APIS", "REST APIs"),
        ("MCP", "MCP"),
        ("RAG", "RAG"),
        ("CHROMADB", "ChromaDB"),
        ("BM25", "BM25"),
        ("PYTHON", "Python"),
        ("SQLITE", "SQLite"),
        ("BASH", "Bash"),
    )


def test_cron_is_not_a_canonical_identifier(config_dir: Path) -> None:
    """The owner deferred crontab -> CRON, so CRON must not ship."""
    policy = load_assessment_config(config_dir).scoring.technology_matching_normalization
    assert "CRON" not in {entry.id for entry in policy.canonical_technologies}
    assert "CRON" not in {family.canonical_id for family in policy.alias_families}


def test_shipped_alias_registry_matches_the_approved_set(config_dir: Path) -> None:
    """A-6: the exact nine families and fifteen variants, never merely a count."""
    policy = load_assessment_config(config_dir).scoring.technology_matching_normalization
    documented = tuple((f.canonical_id, f.variants) for f in policy.alias_families)
    assert documented == APPROVED_ALIAS_FAMILIES
    assert documented == (
        ("REACT", ("react.js", "reactjs")),
        ("REST_APIS", ("rest api", "rest apis", "restful api", "restful apis")),
        ("MCP", ("model context protocol",)),
        ("RAG", ("retrieval-augmented generation", "retrieval augmented generation")),
        ("CHROMADB", ("chroma",)),
        ("BM25", ("okapi bm25",)),
        ("PYTHON", ("python 3", "python3")),
        ("SQLITE", ("sqlite3",)),
        ("BASH", ("bash shell",)),
    )
    assert len(documented) == APPROVED_ALIAS_FAMILY_COUNT == 9
    assert sum(len(v) for _, v in documented) == APPROVED_ALIAS_VARIANT_COUNT == 15


def test_every_shipped_alias_family_carries_approval_date_and_defense(
    config_dir: Path,
) -> None:
    """A-6: an undefended alias family is invalid policy."""
    policy = load_assessment_config(config_dir).scoring.technology_matching_normalization
    for family in policy.alias_families:
        assert family.approval_date == "2026-09-26"
        assert family.defense.strip()


def test_shipped_deferred_alias_variants_are_the_approved_set(config_dir: Path) -> None:
    """A-6: crontab, openssh, JS/TS, javascript/typescript, bare js and ts, and more."""
    policy = load_assessment_config(config_dir).scoring.technology_matching_normalization
    assert frozenset(policy.deferred_alias_variants) == DEFERRED_ALIAS_VARIANTS
    for variant in ("crontab", "openssh", "js/ts", "javascript/typescript", "js", "ts"):
        assert variant in policy.deferred_alias_variants


def test_no_shipped_alias_variant_is_a_deferred_variant(config_dir: Path) -> None:
    policy = load_assessment_config(config_dir).scoring.technology_matching_normalization
    shipped = {v for family in policy.alias_families for v in family.variants}
    assert not shipped & DEFERRED_ALIAS_VARIANTS


def test_candidate_side_compound_parsing_is_deferred(config_dir: Path) -> None:
    """A-6: no dossier compound or parenthetical phrase is parsed."""
    policy = load_assessment_config(config_dir).scoring.technology_matching_normalization
    assert policy.candidate_side_compound_parsing == "deferred"


def test_shipped_required_preferred_policy_is_the_approved_a7_policy(
    config_dir: Path,
) -> None:
    """A-7: preferred technologies have no score, classification, or flag effect."""
    policy = load_assessment_config(
        config_dir
    ).scoring.required_vs_preferred_technology_handling
    assert policy.required_only_dimension_input is True
    assert policy.preferred_score_effect == "none"
    assert policy.preferred_classification_effect == "none"
    assert policy.preferred_recommendation_effect == "none"
    assert policy.preferred_flag_effect == "none"
    assert policy.preferred_raises_required_skill_gap is False
    assert policy.preferred_evidence_map_required is True
    assert policy.preferred_influences_human_next_action_wording_only is True
    assert policy.no_explicit_required_technologies_points == 0
    assert policy.any_of_slot_count == 1
    assert policy.equivalent_may_introduce_new_technology is False
    assert policy.generic_wording_becomes_slot is False
    assert policy.critical_unknown_when_structured_field_yields_no_technology is True
    assert policy.compound_all_of_slot == "deferred"
    assert policy.preferred_extraction == "deferred"


def test_evidence_tier_multipliers_are_unchanged_by_a5(config_dir: Path) -> None:
    """A-5 changed no P-1 value."""
    weights = load_assessment_config(config_dir).scoring.evidence_tier_weighting
    assert (
        weights.TIER_1_VERIFIED_SKILL,
        weights.TIER_2_PROJECT_EVIDENCE,
        weights.TIER_3_EMPLOYMENT_EVIDENCE,
        weights.TIER_4_TRAINING,
    ) == (1.00, 0.70, 0.90, 0.30)


def test_dimension_weights_are_unchanged_by_a5(config_dir: Path) -> None:
    """A-5 scores within the existing 20-point dimension and adds no weight."""
    config = load_assessment_config(config_dir)
    assert sum(config.scoring.weights.values()) == 100
    assert config.scoring.weights["verified_technical_skill_alignment"] == 20
    assert config.evidence_tier_cap_points() == 20


def test_no_alias_target_collides_with_an_enum_member_name(config_dir: Path) -> None:
    """An alias identifier must never be mistakable for a flag, blocker, or tier."""
    policy = load_assessment_config(config_dir).scoring.technology_matching_normalization
    reserved = (
        {flag.value for flag in RiskFlag}
        | {code.value for code in BlockerCode}
        | {tier.value for tier in EvidenceTier}
        | {band.value for band in SalaryCompatibility}
        | {label.value for label in MatchClassification}
    )
    assert not {entry.id for entry in policy.canonical_technologies} & reserved


# ================================================================ no implementation


def test_no_gated_assessment_behaviour_is_implemented() -> None:
    """Everything behind the five remaining policy keys must still refuse to run.

    `match_technologies` and `score_technology_alignment` are deliberately absent from this
    list: the owner permitted dimension-level computation of
    verified_technical_skill_alignment while the gate stands, and they return a
    `TechnologyAlignmentResult`, which carries no total score, classification, recommendation,
    or validation status. `assess_job` remains the gated entry point.
    """
    from vetted.core.assess import blockers, risk_flags, scoring

    for module, name, arity in (
        (blockers, "detect_blockers", 3),
        (blockers, "degree_requirement_is_blocking", 2),
        (risk_flags, "detect_risk_flags", 3),
        (scoring, "assess_compensation", 2),
        (scoring, "assess_job", 3),
    ):
        with pytest.raises(NotImplementedError):
            getattr(module, name)(*[None] * arity)


def test_the_dimension_path_cannot_produce_a_full_assessment() -> None:
    """Ruling 2, enforced by type: no verdict field exists on the dimension result."""
    from vetted.core.domain.assessment import TechnologyAlignmentResult

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
        assert forbidden not in fields


def test_readiness_still_gates_the_full_assessment(config_dir: Path) -> None:
    """Implementing one dimension must not have loosened the five-key gate."""
    with pytest.raises(AssessmentPolicyUnresolvedError):
        load_ready_assessment_config(config_dir)
