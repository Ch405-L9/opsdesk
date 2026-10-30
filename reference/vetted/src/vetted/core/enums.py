"""Single definition site for every CareerOps Local enum.

`RiskFlag`, `Recommendation`, and `ValidationStatus` are derived from PROJECT_GUARDRAILS.md.
`SalaryCompatibility` and `EvidenceTier` are derived from docs/SCORING_DECISIONS.md, the
owner-approved implementation decision record dated 2026-09-25.

`MatchMethod`, `RequirementKind`, `TechnologyGapReason`, and `PolicyStatus` are derived from
the owner-decision records dated 2026-09-26. They have no canonical Markdown source and are
therefore not parity-bound; binding them would require a new labelled section in that record,
which is a separate owner decision.

tests/parity/test_canonical_enum_parity.py fails if any parity-bound enum drifts from its
source document. No enum may be defined or aliased anywhere else in this package.

Every enum below is declared in exactly one of `PARITY_BOUND_ENUMS` or
`SELF_DECLARED_ENUMS`. tests/unit/test_enums.py fails if a new enum is added without being
declared, so the distinction can never go silent.
"""

from enum import StrEnum

__all__ = [
    "PARITY_BOUND_ENUMS",
    "SELF_DECLARED_ENUMS",
    "BlockerCode",
    "EmploymentType",
    "EvidenceTier",
    "MatchClassification",
    "MatchMethod",
    "PolicyStatus",
    "Recommendation",
    "RelocationStatus",
    "RequirementKind",
    "RiskFlag",
    "SalaryCompatibility",
    "TechnologyGapReason",
    "ValidationStatus",
    "WorkArrangementType",
]

PARITY_BOUND_ENUMS: frozenset[str] = frozenset(
    {
        "EvidenceTier",
        "Recommendation",
        "RiskFlag",
        "SalaryCompatibility",
        "ValidationStatus",
    }
)
"""Enums copied from a labelled section of a source document.

Each has a parity test in tests/parity/test_canonical_enum_parity.py that re-reads that
section and fails on drift, because the document is the authority and this module is a copy.
"""

SELF_DECLARED_ENUMS: frozenset[str] = frozenset(
    {
        "BlockerCode",
        "EmploymentType",
        "MatchClassification",
        "MatchMethod",
        "PolicyStatus",
        "RelocationStatus",
        "RequirementKind",
        "TechnologyGapReason",
        "WorkArrangementType",
    }
)
"""Closed sets fixed here, with no prose list anywhere to drift from.

These are not unbound by oversight. A member set implied by an approved rule has one
authority, not two: `MatchMethod` has two members because A-6 prohibits every other matching
route, and `TechnologyGapReason` has four because E-4, E-6, and E-7 produce exactly those.
Writing a Markdown list purely so a parity test could re-read it would create a second
authority and buy nothing.

The risk these carry is an undeclared addition, not drift, so each is guarded by an exact
membership test in tests/unit/test_enums.py instead. Adding a member fails that test.
"""


class ValidationStatus(StrEnum):
    """Evidence status. Source: PROJECT_GUARDRAILS.md, "Evidence statuses"."""

    VERIFIED = "VERIFIED"
    CONCERN = "CONCERN"
    UNVERIFIED = "UNVERIFIED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class MatchClassification(StrEnum):
    """Overall match classification. Thresholds are approved (P-2, resolving A-3)."""

    STRONG_MATCH = "STRONG_MATCH"
    PLAUSIBLE_MATCH = "PLAUSIBLE_MATCH"
    STRETCH = "STRETCH"
    AVOID = "AVOID"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class Recommendation(StrEnum):
    """Human review label. Source: PROJECT_GUARDRAILS.md, "Human-in-the-loop rule".

    No recommendation means "apply automatically".
    """

    REVIEW_FOR_APPLICATION = "REVIEW_FOR_APPLICATION"
    RESEARCH_COMPANY_FIRST = "RESEARCH_COMPANY_FIRST"
    REQUEST_DETAILS_FROM_RECRUITER = "REQUEST_DETAILS_FROM_RECRUITER"
    HOLD_FOR_MISSING_COMPENSATION_OR_LOCATION = "HOLD_FOR_MISSING_COMPENSATION_OR_LOCATION"
    DO_NOT_APPLY = "DO_NOT_APPLY"


class WorkArrangementType(StrEnum):
    US_REMOTE = "US_REMOTE"
    STATE_RESTRICTED_REMOTE = "STATE_RESTRICTED_REMOTE"
    TIME_ZONE_RESTRICTED_REMOTE = "TIME_ZONE_RESTRICTED_REMOTE"
    HYBRID = "HYBRID"
    ON_SITE = "ON_SITE"
    UNKNOWN = "UNKNOWN"


class RelocationStatus(StrEnum):
    PROVIDED = "PROVIDED"
    REQUIRED = "REQUIRED"
    PREFERRED = "PREFERRED"
    NOT_MENTIONED = "NOT_MENTIONED"
    UNKNOWN = "UNKNOWN"


class EmploymentType(StrEnum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    CONTRACT_TO_HIRE = "CONTRACT_TO_HIRE"
    TEMPORARY = "TEMPORARY"
    INTERNSHIP = "INTERNSHIP"
    UNKNOWN = "UNKNOWN"


class SalaryCompatibility(StrEnum):
    """Compensation band. Source: docs/SCORING_DECISIONS.md, decision D-3.

    Supersedes the member list in PROMPT_PHASE_0.md, which named FALLBACK_80K_TO_89K and had
    no BELOW_PREFERRED_REVIEW member. Hourly and contract compensation is never annualized.
    """

    TARGET_90K_PLUS = "TARGET_90K_PLUS"
    FALLBACK_80K_TO_85K = "FALLBACK_80K_TO_85K"
    BELOW_PREFERRED_REVIEW = "BELOW_PREFERRED_REVIEW"
    BELOW_80K = "BELOW_80K"
    CONTRACT_REQUIRES_REVIEW = "CONTRACT_REQUIRES_REVIEW"
    UNKNOWN = "UNKNOWN"


class EvidenceTier(StrEnum):
    """Provenance tier of a technology match. Source: docs/SCORING_DECISIONS.md, decision D-7.

    Reports must disclose which tier produced every technology match. No tier may create an
    unverified skill. Relative tier weighting is approved (P-1, resolving A-4).
    """

    TIER_1_VERIFIED_SKILL = "TIER_1_VERIFIED_SKILL"
    TIER_2_PROJECT_EVIDENCE = "TIER_2_PROJECT_EVIDENCE"
    TIER_3_EMPLOYMENT_EVIDENCE = "TIER_3_EMPLOYMENT_EVIDENCE"
    TIER_4_TRAINING = "TIER_4_TRAINING"


class BlockerCode(StrEnum):
    """The complete hard blocker set.

    Work authorization is deliberately absent: a candidate UNKNOWN can never hard-block (D-5).
    Plain absence of company evidence is deliberately absent: missing evidence is not negative
    evidence (D-6). No salary-override code exists (D-10).
    """

    CLEARANCE_REQUIRED_WITHOUT_CANDIDATE_EVIDENCE = "CLEARANCE_REQUIRED_WITHOUT_CANDIDATE_EVIDENCE"
    MANDATORY_DEGREE_WITHOUT_EQUIVALENCY = "MANDATORY_DEGREE_WITHOUT_EQUIVALENCY"
    EXPLICIT_BASE_SALARY_BELOW_80K = "EXPLICIT_BASE_SALARY_BELOW_80K"
    RESEARCH_HEAVY_UNVERIFIED_QUALIFICATIONS = "RESEARCH_HEAVY_UNVERIFIED_QUALIFICATIONS"
    SENIOR_SCOPE_MATERIALLY_UNSUPPORTED = "SENIOR_SCOPE_MATERIALLY_UNSUPPORTED"
    PAYMENT_OR_IDENTITY_REQUEST = "PAYMENT_OR_IDENTITY_REQUEST"
    AFFIRMATIVE_COMPANY_IDENTITY_CONTRADICTION = "AFFIRMATIVE_COMPANY_IDENTITY_CONTRADICTION"


class RiskFlag(StrEnum):
    """Mandatory risk flags. Source: PROJECT_GUARDRAILS.md, "Mandatory risk flags".

    Exactly 24 members. The band 86,000-89,999 raises no flag from this set and does not
    reuse SALARY_CONFLICT (A-2).
    """

    PAYMENT_REQUEST = "PAYMENT_REQUEST"
    SENSITIVE_IDENTITY_REQUEST = "SENSITIVE_IDENTITY_REQUEST"
    PERSONAL_EMAIL_DOMAIN_RECRUITER = "PERSONAL_EMAIL_DOMAIN_RECRUITER"
    URL_DOMAIN_MISMATCH = "URL_DOMAIN_MISMATCH"
    MISSING_COMPANY_WEBSITE = "MISSING_COMPANY_WEBSITE"
    UNVERIFIABLE_COMPANY = "UNVERIFIABLE_COMPANY"
    COMPENSATION_OUTLIER = "COMPENSATION_OUTLIER"
    JOB_DESCRIPTION_TOO_VAGUE = "JOB_DESCRIPTION_TOO_VAGUE"
    EXCESSIVE_URGENCY = "EXCESSIVE_URGENCY"
    CLEARANCE_REQUIRED = "CLEARANCE_REQUIRED"
    DEGREE_REQUIRED = "DEGREE_REQUIRED"
    WORK_AUTHORIZATION_RESTRICTION = "WORK_AUTHORIZATION_RESTRICTION"
    LOCATION_CONFLICT = "LOCATION_CONFLICT"
    SALARY_CONFLICT = "SALARY_CONFLICT"
    STAFFING_INTERMEDIARY = "STAFFING_INTERMEDIARY"
    END_CLIENT_UNKNOWN = "END_CLIENT_UNKNOWN"
    POSSIBLE_STALE_LISTING = "POSSIBLE_STALE_LISTING"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    SENIORITY_MISMATCH = "SENIORITY_MISMATCH"
    RESEARCH_HEAVY_MISMATCH = "RESEARCH_HEAVY_MISMATCH"
    MISSING_COMPENSATION = "MISSING_COMPENSATION"
    RELOCATION_UNKNOWN = "RELOCATION_UNKNOWN"
    REMOTE_RESTRICTION_UNKNOWN = "REMOTE_RESTRICTION_UNKNOWN"
    REQUIRED_SKILL_GAP = "REQUIRED_SKILL_GAP"


# --------------------------------------------------------------------------------------
# Technology matching. Source: docs/SCORING_DECISIONS.md, owner-decision record dated
# 2026-09-26 (A-5 through A-7). Not parity-bound: no canonical Markdown source exists.
# --------------------------------------------------------------------------------------


class MatchMethod(StrEnum):
    """How a job phrase reached its canonical technology identifier (A-6).

    EXACT and ALIAS resolve a phrase to the same technology. CATEGORY_SUBSTITUTE is different
    in kind: the candidate holds a *different* tool in the same owner-approved substitutable
    category, so it earns reduced credit and the report always names the tool actually used. It
    never claims the requested tool.

    Token matching, substring matching, fuzzy matching, semantic matching, embedding matching,
    LLM matching, and external taxonomy or API lookup remain prohibited, so no member exists
    for them.
    """

    EXACT = "EXACT"
    ALIAS = "ALIAS"
    CATEGORY_SUBSTITUTE = "CATEGORY_SUBSTITUTE"


class RequirementKind(StrEnum):
    """Whether a listing named a technology as required or preferred (A-7).

    Only REQUIRED enters the verified_technical_skill_alignment dimension. PREFERRED has no
    score, classification, recommendation, or flag effect and never raises a skill gap.
    """

    REQUIRED = "REQUIRED"
    PREFERRED = "PREFERRED"


class TechnologyGapReason(StrEnum):
    """Why a required technology slot was not satisfied.

    Rules E-4, E-6, and E-7 are the only sources. NO_EVIDENCE and UNRECOGNIZED_TERM carry no
    tier (E-4). TIER_2_OR_TIER_4_ONLY still raises the gap despite partial credit (E-7).
    PROHIBITED_INFERENCE records the tier that was refused (E-6). There is deliberately no
    member for a preferred-technology gap: preferred technologies never raise one (A-7).

    CORE_LANGUAGE_GAP is the strong signal: the requirement sits in a category the owner marked
    non-substitutable, such as a programming language, and the candidate holds a different
    member of it. Knowing Python does not get you a Rust job, and that is a different fact from
    simply having no evidence.

    CATEGORY_SUBSTITUTE_ONLY is the soft signal: the requirement sits in a substitutable
    category and the candidate holds a peer tool. Reduced credit is granted and the gap is still
    disclosed, so nobody reads the credit as the requested tool.
    """

    NO_EVIDENCE = "NO_EVIDENCE"
    UNRECOGNIZED_TERM = "UNRECOGNIZED_TERM"
    TIER_2_OR_TIER_4_ONLY = "TIER_2_OR_TIER_4_ONLY"
    PROHIBITED_INFERENCE = "PROHIBITED_INFERENCE"
    CORE_LANGUAGE_GAP = "CORE_LANGUAGE_GAP"
    CATEGORY_SUBSTITUTE_ONLY = "CATEGORY_SUBSTITUTE_ONLY"


class PolicyStatus(StrEnum):
    """Standing of one policy decision. Source: the 2026-09-26 dimension-allocation record.

    A gate key with no rule at all is UNRESOLVED and appears in `unresolved_policy`, where the
    only permitted value is the UNRESOLVED sentinel itself.

    PROVISIONAL means a rule exists and the owner approved it as a working default, knowing it
    will be revisited. A provisional rule must be labelled provisional wherever its result is
    displayed: a provisional rule that prints like a settled one is the failure this enum
    exists to prevent.

    APPROVED means the owner settled it. There is deliberately no member for "derived",
    "inferred", or "default": a rule is owner-approved or it does not exist.
    """

    UNRESOLVED = "UNRESOLVED"
    PROVISIONAL = "PROVISIONAL"
    APPROVED = "APPROVED"
