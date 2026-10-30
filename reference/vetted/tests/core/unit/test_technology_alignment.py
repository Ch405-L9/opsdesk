"""Technology matching and the A-5 allocation.

Mechanics are tested against invented candidate terms, so nothing here depends on the real
dossier. The calibration figures at the end use the approved transcription, because those are
the numbers the first true run must reproduce.

Every expected value is computed by hand in the test, never by calling the code under test.
"""

import pytest

from vetted.core.assess.evidence import lookup_key, match_technologies, resolve_job_phrase
from vetted.core.assess.scoring import score_technology_alignment
from vetted.core.config.loader import load_assessment_config
from vetted.core.domain.assessment import TechnologyAlignmentResult
from vetted.core.dossier.terms import CandidateTerm
from vetted.core.enums import (
    EvidenceTier,
    MatchMethod,
    RequirementKind,
    TechnologyGapReason,
)

T1 = EvidenceTier.TIER_1_VERIFIED_SKILL
T2 = EvidenceTier.TIER_2_PROJECT_EVIDENCE
T3 = EvidenceTier.TIER_3_EMPLOYMENT_EVIDENCE
T4 = EvidenceTier.TIER_4_TRAINING

SYNTHETIC_TERMS: tuple[CandidateTerm, ...] = (
    CandidateTerm("Python", T1, "Synthetic skills — Sample section"),
    CandidateTerm("React", T1, "Synthetic skills — Sample section"),
    CandidateTerm("REST APIs", T1, "Synthetic skills — Sample section"),
    CandidateTerm("Kotlin", T2, "Synthetic project — Sample project"),
    CandidateTerm("SQLite", T4, "Synthetic training — Sample course"),
)


@pytest.fixture(scope="module")
def normalization():
    return load_assessment_config().scoring.technology_matching_normalization


@pytest.fixture(scope="module")
def config():
    return load_assessment_config()


# =========================================================== A-6 lookup-key derivation


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Python", "python"),
        ("PYTHON", "python"),
        ("  Python  ", "python"),
        ("REST   APIs", "rest apis"),
        ("React.js", "react.js"),
        ("Python 3", "python 3"),
        ("C++", "c++"),
        ("C#", "c#"),
        (".NET", ".net"),
        ("TCP/IP", "tcp/ip"),
    ],
)
def test_lookup_key_applies_only_the_four_approved_steps(raw: str, expected: str) -> None:
    """NFC, casefold, whitespace collapse, trim. Nothing else.

    Punctuation and version suffixes survive on purpose: stripping them would collide C++
    with C#, mangle .NET, and split TCP/IP.
    """
    assert lookup_key(raw) == expected


def test_lookup_key_is_nfc_stable() -> None:
    """A decomposed and a composed form must produce the same key."""
    assert lookup_key("Rückblick") == lookup_key("Rückblick")


# ================================================================= A-6 phrase resolution


def test_display_name_resolves_exact(normalization) -> None:
    identifier, method, family = resolve_job_phrase("REST APIs", normalization)
    assert (identifier, method, family) == ("REST_APIS", MatchMethod.EXACT, None)


def test_alias_variant_resolves_through_its_family(normalization) -> None:
    identifier, method, family = resolve_job_phrase("React.js", normalization)
    assert (identifier, method, family) == ("REACT", MatchMethod.ALIAS, "REACT")


@pytest.mark.parametrize(
    ("phrase", "identifier"),
    [
        ("reactjs", "REACT"),
        ("RESTful APIs", "REST_APIS"),
        ("model context protocol", "MCP"),
        ("Retrieval-Augmented Generation", "RAG"),
        ("Chroma", "CHROMADB"),
        ("Okapi BM25", "BM25"),
        ("python3", "PYTHON"),
        ("SQLite3", "SQLITE"),
        ("bash shell", "BASH"),
    ],
)
def test_every_approved_alias_variant_resolves(
    normalization, phrase: str, identifier: str
) -> None:
    resolved, method, family = resolve_job_phrase(phrase, normalization)
    assert resolved == identifier
    assert method is MatchMethod.ALIAS
    assert family == identifier


@pytest.mark.parametrize(
    "phrase", ["crontab", "OpenSSH", "JS/TS", "javascript/typescript", "js", "ts"]
)
def test_deferred_variants_never_resolve_to_an_approved_identifier(
    normalization, phrase: str
) -> None:
    """The owner deferred these, so none may reach a canonical identifier."""
    identifier, method, family = resolve_job_phrase(phrase, normalization)
    assert identifier == lookup_key(phrase)
    assert method is MatchMethod.EXACT
    assert family is None


def test_an_unapproved_alias_never_matches(normalization) -> None:
    """A-6: unknown aliases never auto-match. 'ReactJS Native' is not React."""
    identifier, _, family = resolve_job_phrase("ReactJS Native", normalization)
    assert identifier != "REACT"
    assert family is None


# ===================================================================== A-6 no fuzziness


def test_substring_containment_never_matches(normalization) -> None:
    """'React Native' contains 'React'; 'Azure OpenAI' contains 'OpenAI'."""
    matches, gaps = match_technologies(
        ("React Native", "Azure OpenAI"), SYNTHETIC_TERMS, normalization
    )
    assert matches == ()
    assert {gap.raw_job_phrase for gap in gaps} == {"React Native", "Azure OpenAI"}


def test_a_term_is_never_split_into_tokens(normalization) -> None:
    """'Python Django' must not match on the word 'Python'."""
    matches, _ = match_technologies(("Python Django",), SYNTHETIC_TERMS, normalization)
    assert matches == ()


# ============================================================ E-3 and E-8 tier selection


def test_best_tier_wins_when_a_term_holds_several(normalization) -> None:
    """E-3: the highest-weighted evidence, not the first or the last."""
    terms = (
        CandidateTerm("Python", T2, "Synthetic project — Sample project"),
        CandidateTerm("Python", T1, "Synthetic skills — Sample section"),
    )
    matches, gaps = match_technologies(("Python",), terms, normalization)
    assert matches[0].tier is T1
    assert gaps == ()


def test_tier_three_outranks_tier_two(normalization) -> None:
    """E-8: tier ordinal does not imply weight order. Tier 3 is 0.90, Tier 2 is 0.70."""
    terms = (
        CandidateTerm("Python", T2, "Synthetic project — Sample project"),
        CandidateTerm("Python", T3, "Synthetic employment — Sample employer"),
    )
    matches, _ = match_technologies(("Python",), terms, normalization)
    assert matches[0].tier is T3


def test_tier_four_is_the_weakest(normalization) -> None:
    terms = (
        CandidateTerm("Python", T4, "Synthetic training — Sample course"),
        CandidateTerm("Python", T2, "Synthetic project — Sample project"),
    )
    matches, _ = match_technologies(("Python",), terms, normalization)
    assert matches[0].tier is T2


# ================================================================== E-4 and E-7 gaps


def test_no_evidence_scores_nothing_and_raises_a_gap(normalization) -> None:
    """E-4."""
    matches, gaps = match_technologies(("Weaviate",), SYNTHETIC_TERMS, normalization)
    assert matches == ()
    assert len(gaps) == 1
    assert gaps[0].reason is TechnologyGapReason.UNRECOGNIZED_TERM
    assert gaps[0].best_tier_found is None


@pytest.mark.parametrize(("phrase", "tier"), [("Kotlin", T2), ("SQLite", T4)])
def test_partial_credit_still_raises_a_gap(normalization, phrase: str, tier) -> None:
    """E-7: credit and flags are decoupled. A Tier 2 or Tier 4 match scores and still flags."""
    matches, gaps = match_technologies((phrase,), SYNTHETIC_TERMS, normalization)
    assert len(matches) == 1
    assert matches[0].tier is tier
    assert len(gaps) == 1
    assert gaps[0].reason is TechnologyGapReason.TIER_2_OR_TIER_4_ONLY
    assert gaps[0].best_tier_found is tier


def test_tier_one_match_raises_no_gap(normalization) -> None:
    matches, gaps = match_technologies(("Python",), SYNTHETIC_TERMS, normalization)
    assert len(matches) == 1
    assert gaps == ()


# ========================================================== E-5 audit disclosure


def test_every_match_discloses_its_full_audit_trail(normalization) -> None:
    matches, _ = match_technologies(("React.js",), SYNTHETIC_TERMS, normalization)
    match = matches[0]
    assert match.raw_job_phrase == "React.js"
    assert match.normalized_job_identifier == "REACT"
    assert match.raw_candidate_evidence_phrase == "React"
    assert match.normalized_candidate_identifier == "REACT"
    assert match.match_method is MatchMethod.ALIAS
    assert match.alias_family_identifier == "REACT"
    assert match.requirement_kind is RequirementKind.REQUIRED
    assert match.tier is T1
    assert match.evidence_reference == "Synthetic skills — Sample section"


def test_an_exact_match_names_no_alias_family(normalization) -> None:
    matches, _ = match_technologies(("Python",), SYNTHETIC_TERMS, normalization)
    assert matches[0].match_method is MatchMethod.EXACT
    assert matches[0].alias_family_identifier is None


@pytest.mark.parametrize(
    ("phrase", "display"),
    [
        ("React.js", "React"),
        ("reactjs", "React"),
        ("RESTful APIs", "REST APIs"),
        ("python3", "Python"),
        ("Chroma", "ChromaDB"),
        ("okapi bm25", "BM25"),
        ("SQLite3", "SQLite"),
        ("bash shell", "Bash"),
    ],
)
def test_the_human_facing_field_uses_the_approved_display_name(
    normalization, phrase: str, display: str
) -> None:
    """A-6 carried-forward item 4: human-facing output uses the display name.

    Not the listing's own spelling, and not the internal identifier. A listing asking for
    "React.js" is reported as React.
    """
    terms = (
        CandidateTerm("React", T1, "Synthetic skills — Sample section"),
        CandidateTerm("REST APIs", T1, "Synthetic skills — Sample section"),
        CandidateTerm("Python", T1, "Synthetic skills — Sample section"),
        CandidateTerm("ChromaDB", T1, "Synthetic skills — Sample section"),
        CandidateTerm("BM25", T1, "Synthetic skills — Sample section"),
        CandidateTerm("SQLite", T1, "Synthetic skills — Sample section"),
        CandidateTerm("Bash", T1, "Synthetic skills — Sample section"),
    )
    matches, _ = match_technologies((phrase,), terms, normalization)
    assert matches[0].technology == display
    assert matches[0].raw_job_phrase == phrase


def test_an_unregistered_technology_reports_its_own_phrase(normalization) -> None:
    """No approved display name exists for it, so the listing's phrase is the honest label."""
    matches, _ = match_technologies(("Kotlin",), SYNTHETIC_TERMS, normalization)
    assert matches[0].technology == "Kotlin"
    assert matches[0].normalized_job_identifier == "kotlin"


def test_the_display_name_is_never_the_internal_identifier(normalization) -> None:
    """A-6: an identifier is never displayed alone."""
    matches, _ = match_technologies(
        ("REST APIs",),
        (CandidateTerm("REST APIs", T1, "Synthetic skills — Sample section"),),
        normalization,
    )
    assert matches[0].technology == "REST APIs"
    assert matches[0].technology != matches[0].normalized_job_identifier


# ==================================================================== slot counting


def test_duplicate_phrases_collapse_to_one_slot(normalization, config) -> None:
    """Dedupe is by resolved identifier, so keyword repetition cannot inflate a score."""
    result = score_technology_alignment(
        "synthetic-1", ("Python", "python", "PYTHON  ", "python3"), SYNTHETIC_TERMS, config
    )
    assert result.required_slot_count == 1
    assert result.points == 20.0


def test_blank_entries_are_not_slots(normalization, config) -> None:
    result = score_technology_alignment(
        "synthetic-1", ("Python", "", "   "), SYNTHETIC_TERMS, config
    )
    assert result.required_slot_count == 1


# =============================================================== A-5 the formula


def test_the_worked_example_scores_ten_exactly(config) -> None:
    """A-5: Weaviate plus Python, Python evidence only. 20 × (0.00 + 1.00) / 2 = 10.00."""
    result = score_technology_alignment(
        "synthetic-1", ("Weaviate", "Python"), SYNTHETIC_TERMS, config
    )
    assert result.required_slot_count == 2
    assert result.multiplier_sum == 1.00
    assert result.points == 10.00
    assert len(result.gaps) == 1


def test_zero_required_slots_scores_zero_with_no_gap(config) -> None:
    """A-5: and that alone can never produce AVOID or DO_NOT_APPLY (C-3)."""
    result = score_technology_alignment("synthetic-1", (), SYNTHETIC_TERMS, config)
    assert result.required_slot_count == 0
    assert result.points == 0.0
    assert result.gaps == ()
    assert result.matches == ()


def test_all_tier_one_reaches_the_full_dimension_weight(config) -> None:
    """E-1: the cap is the dimension weight, and the formula reaches it without clamping."""
    result = score_technology_alignment(
        "synthetic-1", ("Python", "React", "REST APIs"), SYNTHETIC_TERMS, config
    )
    assert result.multiplier_sum == 3.00
    assert result.points == 20.0
    assert result.points == result.dimension_weight


def test_points_are_exact_and_unrounded(config) -> None:
    """Rounding remains score_rounding_rule: 20 × 2.00 / 3 must stay 40/3."""
    result = score_technology_alignment(
        "synthetic-1", ("Python", "React", "Weaviate"), SYNTHETIC_TERMS, config
    )
    assert result.required_slot_count == 3
    assert result.multiplier_sum == 2.00
    assert result.points == 40 / 3
    assert result.points != round(result.points)


def test_long_required_lists_dilute_proportionally(config) -> None:
    """A-5: no extra penalty beyond proportional dilution."""
    result = score_technology_alignment(
        "synthetic-1",
        ("Python", "React", "REST APIs", "Weaviate", "Pinecone", "Milvus"),
        SYNTHETIC_TERMS,
        config,
    )
    assert result.required_slot_count == 6
    assert result.points == 20 * 3.00 / 6
    assert result.points == 10.0


def test_tier_two_only_scores_partial_credit(config) -> None:
    """20 × 0.70 / 1 = 14.00, and the gap is raised anyway (E-7)."""
    result = score_technology_alignment("synthetic-1", ("Kotlin",), SYNTHETIC_TERMS, config)
    assert result.multiplier_sum == 0.70
    assert result.points == 14.0
    assert len(result.gaps) == 1


def test_the_result_is_the_dimension_type_and_carries_no_verdict(config) -> None:
    """Ruling 2: a dimension figure can never become a full assessment."""
    result = score_technology_alignment("synthetic-1", ("Python",), SYNTHETIC_TERMS, config)
    assert isinstance(result, TechnologyAlignmentResult)
    assert result.dimension == "verified_technical_skill_alignment"
    assert not hasattr(result, "score")
    assert not hasattr(result, "classification")
    assert not hasattr(result, "recommendation")


def test_scoring_is_deterministic(config) -> None:
    args = ("synthetic-1", ("Python", "Kotlin", "Weaviate"), SYNTHETIC_TERMS, config)
    assert score_technology_alignment(*args) == score_technology_alignment(*args)


def test_a_preferred_match_cannot_be_smuggled_into_the_result(normalization) -> None:
    """A-7: the result type rejects any match that is not REQUIRED."""
    from pydantic import ValidationError

    matches, _ = match_technologies(("Python",), SYNTHETIC_TERMS, normalization)
    preferred = matches[0].model_copy(update={"requirement_kind": RequirementKind.PREFERRED})
    with pytest.raises(ValidationError, match="only required technologies"):
        TechnologyAlignmentResult(
            job_id="synthetic-1",
            dimension="verified_technical_skill_alignment",
            dimension_weight=20,
            required_slot_count=1,
            multiplier_sum=1.0,
            points=20.0,
            matches=(preferred,),
        )


# ================================================== category substitution (KISS rule)

CRM_TERMS: tuple[CandidateTerm, ...] = (
    CandidateTerm("Salesforce", T3, "Synthetic employment — Sample employer"),
    CandidateTerm("Python", T1, "Synthetic skills — Sample section"),
)


def test_a_peer_crm_earns_half_credit_and_still_discloses_the_gap(config) -> None:
    """A CRM is a CRM. Holding Salesforce when they ask for Freshdesk is worth something.

    20 x 0.90 x 0.50 = 9.0. The match names Salesforce, never Freshdesk, and the gap is raised
    anyway so reduced credit can never be read as the requested tool.
    """
    result = score_technology_alignment("x", ("Freshdesk",), CRM_TERMS, config)
    assert result.points == 9.0
    match = result.matches[0]
    assert match.match_method is MatchMethod.CATEGORY_SUBSTITUTE
    assert match.technology == "Salesforce"
    assert match.raw_job_phrase == "Freshdesk"
    assert match.alias_family_identifier == "CRM_TICKETING"
    assert match.tier is T3
    assert [gap.reason for gap in result.gaps] == [
        TechnologyGapReason.CATEGORY_SUBSTITUTE_ONLY
    ]


def test_direct_evidence_beats_substitution(config) -> None:
    """Asking for the tool actually held must never downgrade to a substitute."""
    result = score_technology_alignment("x", ("Salesforce",), CRM_TERMS, config)
    assert result.matches[0].match_method is MatchMethod.EXACT
    assert result.points == 18.0
    assert result.gaps == ()


def test_a_tier_one_substitute_is_still_only_half(config) -> None:
    terms = (CandidateTerm("Salesforce", T1, "Synthetic skills — Sample section"),)
    result = score_technology_alignment("x", ("Monday",), terms, config)
    assert result.points == 10.0
    assert result.points != 20.0


def test_a_non_substitutable_miss_earns_nothing_but_names_the_peer(config) -> None:
    """A Rust role needs Rust. Python is a peer language and earns no credit for it."""
    result = score_technology_alignment("x", ("Rust",), CRM_TERMS, config)
    assert result.points == 0.0
    assert result.matches == ()
    gap = result.gaps[0]
    assert gap.reason is TechnologyGapReason.CORE_LANGUAGE_GAP
    assert gap.best_tier_found is T1


def test_a_language_miss_with_no_language_held_is_merely_unrecognized(config) -> None:
    """CORE_LANGUAGE_GAP is the stronger claim, so it needs a peer in the category."""
    terms = (CandidateTerm("Salesforce", T3, "Synthetic employment — Sample employer"),)
    result = score_technology_alignment("x", ("Rust",), terms, config)
    assert result.gaps[0].reason is TechnologyGapReason.UNRECOGNIZED_TERM
    assert result.gaps[0].best_tier_found is None


def test_a_language_hit_survives_a_language_miss(config) -> None:
    """20 x 1.00 / 2 = 10.0: the Rust gap must not erase the Python match."""
    result = score_technology_alignment("x", ("Rust", "Python"), CRM_TERMS, config)
    assert result.points == 10.0
    assert [m.technology for m in result.matches] == ["Python"]


def test_a_substitute_match_must_name_its_category(normalization) -> None:
    """The audit trail records what produced the credit, exactly as for an alias."""
    from pydantic import ValidationError

    from vetted.core.domain.assessment import TechnologyMatch

    payload = {
        "technology": "Salesforce",
        "raw_job_phrase": "Freshdesk",
        "normalized_job_identifier": "freshdesk",
        "raw_candidate_evidence_phrase": "Salesforce",
        "normalized_candidate_identifier": "salesforce",
        "match_method": MatchMethod.CATEGORY_SUBSTITUTE,
        "alias_family_identifier": None,
        "requirement_kind": RequirementKind.REQUIRED,
        "tier": T3,
        "evidence_reference": "Synthetic employment — Sample employer",
    }
    with pytest.raises(ValidationError, match="must name what produced it"):
        TechnologyMatch.model_validate(payload)


def test_substitution_needs_the_candidate_to_hold_a_member(config) -> None:
    """Listing a name in the category table is not candidate evidence."""
    terms = (CandidateTerm("Python", T1, "Synthetic skills — Sample section"),)
    result = score_technology_alignment("x", ("Salesforce",), terms, config)
    assert result.points == 0.0
    assert result.matches == ()
    assert result.gaps[0].reason is TechnologyGapReason.UNRECOGNIZED_TERM
