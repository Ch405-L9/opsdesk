"""Enum membership tests.

These assert the shape the rest of the system depends on. Parity against the source
documents is asserted separately in tests/parity/.

Five enums are copied from a labelled document section and are parity-bound there. The other
eight have no prose list to drift from, so they are guarded here instead by exact membership
assertions. `test_every_enum_declares_its_parity_category` fails if a new enum joins neither
group.
"""


import pytest

from vetted.core import enums
from vetted.core.enums import (
    PARITY_BOUND_ENUMS,
    SELF_DECLARED_ENUMS,
    BlockerCode,
    EvidenceTier,
    MatchClassification,
    MatchMethod,
    PolicyStatus,
    Recommendation,
    RequirementKind,
    RiskFlag,
    SalaryCompatibility,
    TechnologyGapReason,
    ValidationStatus,
)

EXPECTED_RISK_FLAGS = 24


def test_risk_flag_count() -> None:
    assert len(RiskFlag) == EXPECTED_RISK_FLAGS


def test_salary_bands_match_owner_decision() -> None:
    """D-3: the approved band set, superseding PROMPT_PHASE_0.md."""
    assert {member.value for member in SalaryCompatibility} == {
        "TARGET_90K_PLUS",
        "FALLBACK_80K_TO_85K",
        "BELOW_PREFERRED_REVIEW",
        "BELOW_80K",
        "CONTRACT_REQUIRES_REVIEW",
        "UNKNOWN",
    }


def test_superseded_salary_member_is_absent() -> None:
    """The pre-decision member name must not survive anywhere."""
    assert "FALLBACK_80K_TO_89K" not in {member.value for member in SalaryCompatibility}


def test_evidence_tiers_are_the_four_approved_tiers() -> None:
    """D-7."""
    assert [member.value for member in EvidenceTier] == [
        "TIER_1_VERIFIED_SKILL",
        "TIER_2_PROJECT_EVIDENCE",
        "TIER_3_EMPLOYMENT_EVIDENCE",
        "TIER_4_TRAINING",
    ]


def test_work_authorization_is_not_a_blocker_code() -> None:
    """D-5: a candidate UNKNOWN can never hard-block."""
    assert not [code for code in BlockerCode if "AUTHORIZATION" in code.value]


def test_missing_company_evidence_is_not_a_blocker_code() -> None:
    """D-6: missing evidence is not negative evidence."""
    assert not [code for code in BlockerCode if "MISSING" in code.value]


def test_no_salary_override_blocker_code() -> None:
    """D-10: the override is deferred, so no code may exist for it."""
    assert not [code for code in BlockerCode if "OVERRIDE" in code.value]


def test_recommendation_has_no_automatic_apply_member() -> None:
    """No recommendation means "apply automatically"."""
    assert not [r for r in Recommendation if "AUTO" in r.value]


def test_insufficient_evidence_available_on_both_status_enums() -> None:
    """D-5 requires marking an assessment INSUFFICIENT_EVIDENCE."""
    assert ValidationStatus.INSUFFICIENT_EVIDENCE
    assert MatchClassification.INSUFFICIENT_EVIDENCE


# ------------------------------------------------- technology matching (A-5 to A-7)


def test_match_method_has_exactly_the_approved_routes() -> None:
    """A-6 plus the owner-approved category-substitution route."""
    assert [member.value for member in MatchMethod] == [
        "EXACT",
        "ALIAS",
        "CATEGORY_SUBSTITUTE",
    ]


def test_no_prohibited_match_method_member_exists() -> None:
    """A-6 bars token, substring, fuzzy, semantic, embedding, LLM, and taxonomy matching."""
    members = {member.value for member in MatchMethod}
    for prohibited in (
        "TOKEN",
        "SUBSTRING",
        "FUZZY",
        "SEMANTIC",
        "EMBEDDING",
        "LLM",
        "TAXONOMY",
        "API",
    ):
        assert not [name for name in members if prohibited in name], (
            f"{prohibited} matching is prohibited and must have no member"
        )


def test_requirement_kind_is_required_or_preferred() -> None:
    """A-7."""
    assert [member.value for member in RequirementKind] == ["REQUIRED", "PREFERRED"]


def test_technology_gap_reasons_are_the_approved_reasons() -> None:
    """E-4, E-6, E-7, plus the two owner-approved category signals."""
    assert [member.value for member in TechnologyGapReason] == [
        "NO_EVIDENCE",
        "UNRECOGNIZED_TERM",
        "TIER_2_OR_TIER_4_ONLY",
        "PROHIBITED_INFERENCE",
        "CORE_LANGUAGE_GAP",
        "CATEGORY_SUBSTITUTE_ONLY",
    ]


def test_no_preferred_gap_reason_exists() -> None:
    """A-7: preferred technologies never raise a skill gap."""
    assert not [r for r in TechnologyGapReason if "PREFERRED" in r.value]


def test_policy_status_has_no_inferred_or_default_member() -> None:
    """A rule is owner-approved or it does not exist. Nothing derives its own standing."""
    members = {member.value for member in PolicyStatus}
    assert members == {"UNRESOLVED", "PROVISIONAL", "APPROVED"}
    for forbidden in ("DERIVED", "INFERRED", "DEFAULT", "ASSUMED", "AUTO"):
        assert not [m for m in members if forbidden in m]


def test_a5_to_a7_added_no_risk_flag_or_blocker_code() -> None:
    """The flag and blocker sets stay parity-locked to PROJECT_GUARDRAILS.md."""
    assert len(RiskFlag) == EXPECTED_RISK_FLAGS
    assert len(BlockerCode) == 7
    assert "PREFERRED_SKILL_GAP" not in {flag.value for flag in RiskFlag}
    assert "UNKNOWN_TERM" not in {flag.value for flag in RiskFlag}
    assert RiskFlag.REQUIRED_SKILL_GAP.value == "REQUIRED_SKILL_GAP"


def test_technology_matching_enums_are_exported() -> None:
    """The definition-site sweep below requires every enum to be named in __all__."""
    for name in ("MatchMethod", "RequirementKind", "TechnologyGapReason"):
        assert name in enums.__all__


# --------------------------------------------------- the parity partition is complete


def _enum_names() -> set[str]:
    """Every enum this module exports, by name."""
    from enum import Enum

    return {
        name
        for name in enums.__all__
        if isinstance(getattr(enums, name), type)
        and issubclass(getattr(enums, name), Enum)
    }


def test_every_enum_declares_its_parity_category() -> None:
    """A new enum must be declared parity-bound or self-declared. Silence is a failure.

    This is the control that keeps the distinction honest: eight of the thirteen enums have
    no source document, and without this test that fact is invisible to the next author.
    """
    declared = PARITY_BOUND_ENUMS | SELF_DECLARED_ENUMS
    names = _enum_names()
    assert names - declared == set(), (
        f"undeclared enum(s): {sorted(names - declared)}. Add each to PARITY_BOUND_ENUMS "
        "if it is copied from a labelled document section, or to SELF_DECLARED_ENUMS if its "
        "member set is fixed by an approved rule with no prose list."
    )
    assert declared - names == set(), (
        f"declared but missing enum(s): {sorted(declared - names)}"
    )


def test_the_two_parity_categories_are_disjoint() -> None:
    assert not PARITY_BOUND_ENUMS & SELF_DECLARED_ENUMS



# Exact member sets for every self-declared enum, in declaration order. A count is never
# sufficient: a renamed or swapped member must fail as loudly as an added one.
SELF_DECLARED_MEMBERS: dict[str, tuple[str, ...]] = {
    "BlockerCode": (
        "CLEARANCE_REQUIRED_WITHOUT_CANDIDATE_EVIDENCE",
        "MANDATORY_DEGREE_WITHOUT_EQUIVALENCY",
        "EXPLICIT_BASE_SALARY_BELOW_80K",
        "RESEARCH_HEAVY_UNVERIFIED_QUALIFICATIONS",
        "SENIOR_SCOPE_MATERIALLY_UNSUPPORTED",
        "PAYMENT_OR_IDENTITY_REQUEST",
        "AFFIRMATIVE_COMPANY_IDENTITY_CONTRADICTION",
    ),
    "EmploymentType": (
        "FULL_TIME",
        "PART_TIME",
        "CONTRACT",
        "CONTRACT_TO_HIRE",
        "TEMPORARY",
        "INTERNSHIP",
        "UNKNOWN",
    ),
    "MatchClassification": (
        "STRONG_MATCH",
        "PLAUSIBLE_MATCH",
        "STRETCH",
        "AVOID",
        "INSUFFICIENT_EVIDENCE",
    ),
    "MatchMethod": ("EXACT", "ALIAS", "CATEGORY_SUBSTITUTE"),
    "PolicyStatus": ("UNRESOLVED", "PROVISIONAL", "APPROVED"),
    "RelocationStatus": (
        "PROVIDED",
        "REQUIRED",
        "PREFERRED",
        "NOT_MENTIONED",
        "UNKNOWN",
    ),
    "RequirementKind": ("REQUIRED", "PREFERRED"),
    "TechnologyGapReason": (
        "NO_EVIDENCE",
        "UNRECOGNIZED_TERM",
        "TIER_2_OR_TIER_4_ONLY",
        "PROHIBITED_INFERENCE",
        "CORE_LANGUAGE_GAP",
        "CATEGORY_SUBSTITUTE_ONLY",
    ),
    "WorkArrangementType": (
        "US_REMOTE",
        "STATE_RESTRICTED_REMOTE",
        "TIME_ZONE_RESTRICTED_REMOTE",
        "HYBRID",
        "ON_SITE",
        "UNKNOWN",
    ),
}


def test_every_self_declared_enum_has_an_exact_member_set() -> None:
    """The table must cover exactly the self-declared enums, so none can slip through."""
    assert set(SELF_DECLARED_MEMBERS) == SELF_DECLARED_ENUMS


@pytest.mark.parametrize("name", sorted(SELF_DECLARED_MEMBERS))
def test_self_declared_enum_members_are_exact(name: str) -> None:
    """A self-declared enum has no source document, so this is its only guard."""
    members = tuple(member.value for member in getattr(enums, name))
    assert members == SELF_DECLARED_MEMBERS[name]


def test_enums_module_is_the_only_definition_site() -> None:
    """No enum may be defined or aliased outside vetted.core.enums."""
    import pkgutil
    from enum import Enum

    import vetted.core

    declared = {name for name in enums.__all__}
    for module_info in pkgutil.walk_packages(vetted.core.__path__, "vetted.core."):
        if module_info.name == "vetted.core.enums":
            continue
        module = __import__(module_info.name, fromlist=["_"])
        for attr_name, attr in vars(module).items():
            if isinstance(attr, type) and issubclass(attr, Enum) and attr.__module__ != "enum":
                assert attr.__module__ == "vetted.core.enums", (
                    f"{module_info.name}.{attr_name} defines an enum outside vetted.core.enums"
                )
                assert attr_name in declared or attr_name.startswith("_")
