"""Configuration schemas.

Two distinct validation stages, kept separate on purpose:

1. Structural validation parses and type-checks the shipped configuration. It succeeds
   while policy decisions remain outstanding, so import, lint, type check, test, and CLI
   help all work.
2. Readiness validation is a separate, explicit step that fails while any key in
   `REQUIRED_UNRESOLVED_POLICY_KEYS` is still the UNRESOLVED sentinel.

Policy source: docs/SCORING_DECISIONS.md, owner-decision records dated 2026-09-25
(P-1 through P-6) and 2026-09-26 (A-5 through A-7). No assessment behaviour is implemented
here. The A-5 through A-7 models below validate policy data only: no allocation, no
normalization of listing or dossier text, and no technology matching is performed.
"""

import re
import unicodedata
from collections.abc import Sequence
from typing import Any, Final, Literal

from pydantic import field_validator, model_validator

from vetted.core.domain import FrozenModel
from vetted.core.enums import (
    BlockerCode,
    MatchClassification,
    PolicyStatus,
    RiskFlag,
    SalaryCompatibility,
)

__all__ = [
    "ALLOCATION_RULE_DIMENSIONS",
    "ALLOCATION_RULE_KEYS",
    "APPROVED_ALIAS_FAMILIES",
    "APPROVED_ALIAS_FAMILY_COUNT",
    "APPROVED_ALIAS_VARIANT_COUNT",
    "APPROVED_CANONICAL_TECHNOLOGIES",
    "APPROVED_NORMALIZATION_STEPS",
    "APPROVED_REPORT_ORDER",
    "DEFERRED_ALIAS_VARIANTS",
    "REQUIRED_UNRESOLVED_POLICY_KEYS",
    "UNRESOLVED",
    "AliasFamily",
    "AssessmentConfig",
    "AssessmentPolicyUnresolvedError",
    "BlockerConfig",
    "BlockerRule",
    "CanonicalTechnology",
    "ClassificationBand",
    "ClassificationThresholds",
    "CompensationBand",
    "CompensationConfig",
    "EvidenceTierWeights",
    "MarketReference",
    "MarketReferenceRow",
    "RegionalPriceParity",
    "ReportDisplayPolicy",
    "RequiredPreferredPolicy",
    "RiskFlagConfig",
    "RiskFlagRule",
    "SalaryTargets",
    "ScoringConfig",
    "SeniorScopeRule",
    "SeniorityBand",
    "SeniorityBands",
    "SubstitutionCredit",
    "TechnologyAllocationPolicy",
    "TechnologyCategories",
    "TechnologyCategory",
    "TechnologyNormalizationPolicy",
    "Unresolved",
]

UNRESOLVED: Final = "UNRESOLVED"
"""Sentinel for a policy decision the owner has not yet approved. Never invent a value."""

Unresolved = Literal["UNRESOLVED"]

EXPECTED_WEIGHT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "role_family_relevance",
        "verified_technical_skill_alignment",
        "responsibility_and_project_evidence_alignment",
        "seniority_and_documented_evidence_compatibility",
        "compensation_compatibility",
        "location_remote_relocation_compatibility",
        "employment_type_compatibility",
        "employer_listing_validation_quality",
        "growth_learning_relevance",
    }
)
"""The nine scoring dimensions. The 15-point dimension is named per D-4."""

TOTAL_WEIGHT: Final = 100
MIN_SCORE: Final = 0
MAX_SCORE: Final = 100

REQUIRED_UNRESOLVED_POLICY_KEYS: Final[tuple[str, ...]] = (
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
"""Policy decisions that gate assessment readiness. Order is the approved order.

Eight keys originally gated readiness. Three were resolved by the 2026-09-26
technology-matching record - `technology_base_credit_allocation` (A-5),
`technology_matching_normalization` (A-6), and `required_vs_preferred_technology_handling`
(A-7) - and are now typed policy blocks on `ScoringConfig`.

Six allocation-rule keys were then added by the 2026-09-26 dimension-allocation record, one
for each dimension that holds an approved weight but no rule for turning facts into points.
Those dimensions account for 55 of the 100 points and were absent from this gate entirely,
which made the gap invisible. Making already-missing work visible is not a regression.

A key is resolved only by removing it from this tuple and from `unresolved_policy` together,
and adding a typed policy block that carries its own `PolicyStatus`.
"""

ALLOCATION_RULE_KEYS: Final[tuple[str, ...]] = (
    "role_family_allocation_rule",
    "responsibility_evidence_allocation_rule",
    "location_remote_relocation_allocation_rule",
    "employment_type_allocation_rule",
    "growth_learning_allocation_rule",
    "employer_listing_validation_allocation_rule",
)
"""The six dimension-allocation keys, in the order their dimensions are weighted."""

ALLOCATION_RULE_DIMENSIONS: Final[dict[str, str]] = {
    "role_family_allocation_rule": "role_family_relevance",
    "responsibility_evidence_allocation_rule": (
        "responsibility_and_project_evidence_alignment"
    ),
    "location_remote_relocation_allocation_rule": (
        "location_remote_relocation_compatibility"
    ),
    "employment_type_allocation_rule": "employment_type_compatibility",
    "growth_learning_allocation_rule": "growth_learning_relevance",
    "employer_listing_validation_allocation_rule": "employer_listing_validation_quality",
}
"""Each allocation key to the scoring dimension it governs. Every value is a weight key."""

APPROVED_SENIORITY_POINTS: Final[tuple[int, ...]] = (15, 11, 7, 3, 0)
"""P-3 point bands, in descending order."""

APPROVED_REPORT_ORDER: Final[tuple[str, ...]] = (
    "Recommendation",
    "Hard blockers",
    "Validation status and risk flags",
    "Critical unknowns / missing evidence",
    "Match classification and score",
    "Per-dimension score breakdown",
    "Evidence-tier map with candidate-proof references",
    "Human next action",
)
"""P-6 report section order. The score sits at position 5 and is never a headline."""

APPROVED_SENIOR_SCOPE_CATEGORIES: Final[tuple[str, ...]] = (
    "leadership_or_ownership",
    "five_plus_years_required",
    "mlops_cloud_or_platform_ownership",
    "kubernetes_terraform_docker_core",
    "research_training_or_publications",
    "unsupported_scale_or_ownership_claims",
    "clearance_or_independent_blocker",
)
"""P-5 materially-unsupported requirement categories."""

MINIMUM_UNSUPPORTED_REQUIREMENTS: Final = 2
"""P-5: a senior title alone can never block."""

SCORED_CLASSIFICATIONS: Final[frozenset[MatchClassification]] = frozenset(
    {
        MatchClassification.STRONG_MATCH,
        MatchClassification.PLAUSIBLE_MATCH,
        MatchClassification.STRETCH,
        MatchClassification.AVOID,
    }
)
"""INSUFFICIENT_EVIDENCE is excluded: it is reachable only through the C-4 cap."""

APPROVED_ALLOCATION_DIMENSION: Final = "verified_technical_skill_alignment"
"""A-5: the only dimension the allocation formula may score."""

APPROVED_NORMALIZATION_STEPS: Final[tuple[str, ...]] = (
    "nfc",
    "casefold",
    "collapse_whitespace",
    "trim",
)
"""A-6: the only permitted lookup-key derivation steps, in order.

No punctuation stripping, version stripping, acronym expansion, token matching, substring
matching, fuzzy matching, semantic matching, embedding matching, LLM matching, external
taxonomy lookup, or API lookup is permitted.
"""

APPROVED_CANONICAL_TECHNOLOGIES: Final[tuple[tuple[str, str], ...]] = (
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
"""A-6 canonical identifiers paired with their single approved display name.

Identifiers are internal. Human-facing output uses the display name. `CRON` is deliberately
absent: the owner deferred it.
"""

APPROVED_ALIAS_FAMILIES: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
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
"""A-6 initial approved alias registry: variant lookup key to canonical identifier.

Rows are one-way. A canonical identifier may exist for a technology absent from candidate
evidence; a requirement normalizing to it simply finds no evidence and raises
REQUIRED_SKILL_GAP under A-5.
"""

APPROVED_ALIAS_FAMILY_COUNT: Final = 9
APPROVED_ALIAS_VARIANT_COUNT: Final = 15

DEFERRED_ALIAS_VARIANTS: Final[frozenset[str]] = frozenset(
    {
        "crontab",
        "openssh",
        "js/ts",
        "javascript/typescript",
        "js",
        "ts",
        "react native",
        "ubuntu",
        "vector database",
    }
)
"""A-6 variant lookup keys the owner explicitly deferred. None may appear in a family."""

CANONICAL_ID_PATTERN: Final = re.compile(r"^[A-Z][A-Z0-9_]*$")
"""A-6 canonical identifiers are uppercase-snake."""

BARE_ACRONYM_LENGTH: Final = 2
"""A-6: no bare two-letter acronym becomes an alias. `TS` also denotes Top Secret."""


def _lookup_key(value: str) -> str:
    """Derive a lookup key using only the four approved A-6 steps, in order.

    Exists solely to validate that shipped alias variants are already normalized. No
    listing text and no dossier text is normalized here, and no technology matching is
    performed: matching remains unimplemented, separately approved work.
    """
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


class AssessmentPolicyUnresolvedError(RuntimeError):
    """Raised when full assessment execution is requested before policy is approved."""

    def __init__(self, keys: Sequence[str]) -> None:
        self.unresolved_keys: tuple[str, ...] = tuple(keys)
        joined = ", ".join(self.unresolved_keys)
        super().__init__(
            f"Assessment policy is not ready. Unresolved keys: {joined}. "
            "These require explicit owner approval, recorded in docs/SCORING_DECISIONS.md, "
            "before assessment behaviour may be implemented or executed. "
            "No value may be invented."
        )


class EvidenceTierWeights(FrozenModel):
    """P-1 evidence-tier multipliers.

    Applied only within `verified_technical_skill_alignment` and capped at that
    dimension's weight (E-1). Tier ordinal does not imply weight order: Tier 3 outranks
    Tier 2 under this policy (E-8).
    """

    TIER_1_VERIFIED_SKILL: float
    TIER_2_PROJECT_EVIDENCE: float
    TIER_3_EMPLOYMENT_EVIDENCE: float
    TIER_4_TRAINING: float

    @model_validator(mode="after")
    def _check_multipliers(self) -> "EvidenceTierWeights":
        values = {name: getattr(self, name) for name in self.__class__.model_fields}
        for name, value in values.items():
            if not 0.0 < value <= 1.0:
                raise ValueError(f"tier multiplier {name} must be in (0.0, 1.0], got {value}")
        if self.TIER_1_VERIFIED_SKILL != 1.0:
            raise ValueError("TIER_1_VERIFIED_SKILL is the reference tier and must equal 1.0")
        if max(values.values()) != self.TIER_1_VERIFIED_SKILL:
            raise ValueError("no tier may exceed TIER_1_VERIFIED_SKILL")
        return self


class ClassificationBand(FrozenModel):
    """One classification band. Both bounds inclusive."""

    classification: MatchClassification
    min_score: int
    max_score: int

    @model_validator(mode="after")
    def _check_band(self) -> "ClassificationBand":
        if self.min_score > self.max_score:
            raise ValueError(f"{self.classification}: min_score exceeds max_score")
        if self.min_score < MIN_SCORE or self.max_score > MAX_SCORE:
            raise ValueError(f"{self.classification}: band falls outside {MIN_SCORE}-{MAX_SCORE}")
        return self


class ClassificationThresholds(FrozenModel):
    """P-2 global classification bands. Must tile 0-100 with no gap and no overlap."""

    bands: tuple[ClassificationBand, ...]

    @model_validator(mode="after")
    def _check_tiling(self) -> "ClassificationThresholds":
        present = {band.classification for band in self.bands}
        if len(present) != len(self.bands):
            raise ValueError("duplicate classification in thresholds")
        if present != SCORED_CLASSIFICATIONS:
            missing = sorted(c.value for c in SCORED_CLASSIFICATIONS - present)
            unexpected = sorted(c.value for c in present - SCORED_CLASSIFICATIONS)
            raise ValueError(
                f"classification bands are wrong. missing={missing} unexpected={unexpected}"
            )
        ordered = sorted(self.bands, key=lambda b: b.min_score)
        if ordered[0].min_score != MIN_SCORE:
            raise ValueError(f"the lowest classification band must begin at {MIN_SCORE}")
        if ordered[-1].max_score != MAX_SCORE:
            raise ValueError(f"the highest classification band must end at {MAX_SCORE}")
        for lower, upper in zip(ordered, ordered[1:], strict=False):
            if lower.max_score + 1 != upper.min_score:
                raise ValueError(
                    "classification bands must tile with no gap and no overlap: "
                    f"{lower.classification} ends at {lower.max_score} but "
                    f"{upper.classification} begins at {upper.min_score}"
                )
        return self


class SeniorityBand(FrozenModel):
    """One P-3 seniority point band."""

    points: int
    description: str


class SeniorityBands(FrozenModel):
    """P-3 seniority and documented-evidence compatibility bands, 15 points."""

    bands: tuple[SeniorityBand, ...]

    @model_validator(mode="after")
    def _check_bands(self) -> "SeniorityBands":
        points = [band.points for band in self.bands]
        if tuple(points) != APPROVED_SENIORITY_POINTS:
            raise ValueError(
                f"seniority point bands must be {list(APPROVED_SENIORITY_POINTS)} "
                f"in descending order, got {points}"
            )
        if any(not band.description.strip() for band in self.bands):
            raise ValueError("every seniority band requires a description")
        return self


class ReportDisplayPolicy(FrozenModel):
    """P-6 report section order and the anti-headline rule."""

    order: tuple[str, ...]
    score_never_headline: bool

    @model_validator(mode="after")
    def _check_order(self) -> "ReportDisplayPolicy":
        if self.order != APPROVED_REPORT_ORDER:
            raise ValueError(
                "report display order must be the approved eight-step sequence, "
                f"got {list(self.order)}"
            )
        if not self.score_never_headline:
            raise ValueError("score_never_headline must be true; the score is never a headline")
        return self


class TechnologyAllocationPolicy(FrozenModel):
    """A-5 required-only conservative allocation. Policy data only; nothing is computed.

    points = 20 x (sum of required-slot best-tier multipliers) / number of required slots,
    when there is at least one required slot; 0 when there are none. Preferred technologies
    never enter the numerator or the denominator. The result stays exact and unrounded:
    rounding remains the unresolved `score_rounding_rule` key.
    """

    dimension: str
    allocation: Literal["required_only_conservative"]
    zero_required_slots_points: int
    preferred_in_numerator: bool
    preferred_in_denominator: bool
    unrecognized_required_term_credit: float
    unrecognized_required_term_stays_in_denominator: bool
    numerator_source: Literal["structured_technology_fields_only"]
    prose_token_scanning: bool
    rounding: Literal["deferred_to_score_rounding_rule"]

    @model_validator(mode="after")
    def _check_policy(self) -> "TechnologyAllocationPolicy":
        if self.dimension != APPROVED_ALLOCATION_DIMENSION:
            raise ValueError(
                f"allocation dimension must be {APPROVED_ALLOCATION_DIMENSION!r} (E-1), "
                f"got {self.dimension!r}"
            )
        if self.zero_required_slots_points != 0:
            raise ValueError("zero required slots must score 0 points under A-5")
        if self.preferred_in_numerator or self.preferred_in_denominator:
            raise ValueError(
                "A-5: preferred technologies never enter the numerator or the denominator"
            )
        if self.unrecognized_required_term_credit != 0.0:
            raise ValueError("an unrecognized required term receives zero credit under A-5")
        if not self.unrecognized_required_term_stays_in_denominator:
            raise ValueError(
                "A-5: an unrecognized required term stays in the denominator and is never "
                "silently ignored"
            )
        if self.prose_token_scanning:
            raise ValueError("A-5: raw listing prose is never token-scanned for score")
        return self


class CanonicalTechnology(FrozenModel):
    """One A-6 canonical identifier and its single approved display name."""

    id: str
    display_name: str

    @model_validator(mode="after")
    def _check_identifier(self) -> "CanonicalTechnology":
        if CANONICAL_ID_PATTERN.match(self.id) is None:
            raise ValueError(
                f"canonical identifier must be uppercase-snake, got {self.id!r}"
            )
        if not self.display_name.strip():
            raise ValueError(f"{self.id}: a canonical identifier requires a display name")
        return self


class AliasFamily(FrozenModel):
    """One A-6 alias family: variant lookup keys mapping one-way to a canonical identifier.

    Every family requires an approval date and a short owner-approved defense statement
    explaining why each member is the same technology rather than a related one.
    """

    canonical_id: str
    approval_date: str
    defense: str
    variants: tuple[str, ...]

    @model_validator(mode="after")
    def _check_family(self) -> "AliasFamily":
        if CANONICAL_ID_PATTERN.match(self.canonical_id) is None:
            raise ValueError(
                f"canonical identifier must be uppercase-snake, got {self.canonical_id!r}"
            )
        if not self.approval_date.strip():
            raise ValueError(f"{self.canonical_id}: alias family requires an approval date")
        if not self.defense.strip():
            raise ValueError(
                f"{self.canonical_id}: alias family requires a defense statement"
            )
        if not self.variants:
            raise ValueError(f"{self.canonical_id}: alias family requires variants")
        if len(set(self.variants)) != len(self.variants):
            raise ValueError(f"{self.canonical_id}: duplicate variant in alias family")
        for variant in self.variants:
            if variant != _lookup_key(variant):
                raise ValueError(
                    f"{self.canonical_id}: alias variant {variant!r} is not already a "
                    "normalized lookup key under the four approved steps"
                )
            if len(variant) == BARE_ACRONYM_LENGTH and variant.isalpha():
                raise ValueError(
                    f"{self.canonical_id}: no bare two-letter acronym may become an alias, "
                    f"got {variant!r}"
                )
            if variant in DEFERRED_ALIAS_VARIANTS:
                raise ValueError(
                    f"{self.canonical_id}: alias variant {variant!r} is explicitly deferred "
                    "and may not be used"
                )
        return self


class TechnologyNormalizationPolicy(FrozenModel):
    """A-6 controlled alias families with review queue. Policy data only.

    Candidate-side compound and parenthetical parsing is deferred, so no dossier phrase is
    parsed or normalized here. No matching is performed.
    """

    normalization_steps: tuple[str, ...]
    whole_phrase_only: bool
    alias_direction: Literal["variant_to_canonical"]
    unknown_alias_auto_match: bool
    bare_two_letter_aliases_allowed: bool
    candidate_side_compound_parsing: Literal["deferred"]
    unknown_term_handling: Literal["report_section_only"]
    persistent_review_queue: bool
    canonical_technologies: tuple[CanonicalTechnology, ...]
    alias_families: tuple[AliasFamily, ...]
    deferred_alias_variants: tuple[str, ...]
    deferred_alias_mappings: tuple[str, ...]
    deferred_alias_categories: tuple[str, ...]

    @model_validator(mode="after")
    def _check_mechanics(self) -> "TechnologyNormalizationPolicy":
        if self.normalization_steps != APPROVED_NORMALIZATION_STEPS:
            raise ValueError(
                "normalization steps must be exactly "
                f"{list(APPROVED_NORMALIZATION_STEPS)}, got {list(self.normalization_steps)}"
            )
        if not self.whole_phrase_only:
            raise ValueError("A-6: alias matching is whole-phrase only")
        if self.unknown_alias_auto_match:
            raise ValueError("A-6: unknown aliases never auto-match")
        if self.bare_two_letter_aliases_allowed:
            raise ValueError("A-6: no bare two-letter acronym becomes an alias")
        if self.persistent_review_queue:
            raise ValueError("A-6: no persistent review queue is added; persistence is barred")
        return self

    @model_validator(mode="after")
    def _check_registry(self) -> "TechnologyNormalizationPolicy":
        ids = [entry.id for entry in self.canonical_technologies]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate canonical identifier in the display-name registry")
        known = set(ids)
        seen: dict[str, str] = {}
        for family in self.alias_families:
            if family.canonical_id not in known:
                raise ValueError(
                    f"alias family targets {family.canonical_id!r}, which has no approved "
                    "display name"
                )
            for variant in family.variants:
                if variant in seen:
                    raise ValueError(
                        f"alias variant {variant!r} maps to both {seen[variant]!r} and "
                        f"{family.canonical_id!r}"
                    )
                seen[variant] = family.canonical_id
        targets = [family.canonical_id for family in self.alias_families]
        if len(set(targets)) != len(targets):
            raise ValueError("duplicate canonical identifier across alias families")
        return self

    @model_validator(mode="after")
    def _check_approved_sets(self) -> "TechnologyNormalizationPolicy":
        documented = tuple(
            (entry.id, entry.display_name) for entry in self.canonical_technologies
        )
        if documented != APPROVED_CANONICAL_TECHNOLOGIES:
            raise ValueError(
                "canonical technologies must be the approved identifier and display-name "
                f"registry, got {[list(pair) for pair in documented]}"
            )
        families = tuple(
            (family.canonical_id, family.variants) for family in self.alias_families
        )
        if families != APPROVED_ALIAS_FAMILIES:
            raise ValueError(
                "alias families must be the approved initial registry, got "
                f"{[family[0] for family in families]}"
            )
        if len(self.alias_families) != APPROVED_ALIAS_FAMILY_COUNT:
            raise ValueError(
                f"alias families must number {APPROVED_ALIAS_FAMILY_COUNT}, "
                f"got {len(self.alias_families)}"
            )
        variant_total = sum(len(family.variants) for family in self.alias_families)
        if variant_total != APPROVED_ALIAS_VARIANT_COUNT:
            raise ValueError(
                f"alias variants must number {APPROVED_ALIAS_VARIANT_COUNT}, "
                f"got {variant_total}"
            )
        if frozenset(self.deferred_alias_variants) != DEFERRED_ALIAS_VARIANTS:
            raise ValueError(
                "deferred alias variants must be the approved deferred set, got "
                f"{sorted(self.deferred_alias_variants)}"
            )
        if not self.deferred_alias_mappings:
            raise ValueError("the approved deferred alias mappings must be recorded")
        if not self.deferred_alias_categories:
            raise ValueError("the approved deferred alias categories must be recorded")
        return self


class RequiredPreferredPolicy(FrozenModel):
    """A-7 required-primary with preferred informational only. Policy data only.

    Preferred-technology extraction, its schema, any capture-template change, and the
    compound ALL-OF slot are all deferred and unimplemented.
    """

    required_only_dimension_input: bool
    preferred_score_effect: Literal["none"]
    preferred_classification_effect: Literal["none"]
    preferred_recommendation_effect: Literal["none"]
    preferred_flag_effect: Literal["none"]
    preferred_raises_required_skill_gap: bool
    preferred_evidence_map_required: bool
    preferred_influences_human_next_action_wording_only: bool
    no_explicit_required_technologies_points: int
    any_of_slot_count: int
    equivalent_may_introduce_new_technology: bool
    generic_wording_becomes_slot: bool
    critical_unknown_when_structured_field_yields_no_technology: bool
    compound_all_of_slot: Literal["deferred"]
    preferred_extraction: Literal["deferred"]

    @model_validator(mode="after")
    def _check_policy(self) -> "RequiredPreferredPolicy":
        if not self.required_only_dimension_input:
            raise ValueError(
                "A-7: required technologies are the only input to the technical-alignment "
                "dimension"
            )
        if self.preferred_raises_required_skill_gap:
            raise ValueError("A-7: preferred technologies never raise REQUIRED_SKILL_GAP")
        if not self.preferred_evidence_map_required:
            raise ValueError("A-7: a future report must show a preferred-evidence map")
        if not self.preferred_influences_human_next_action_wording_only:
            raise ValueError(
                "A-7: preferred alignment may influence only Human next action wording"
            )
        if self.no_explicit_required_technologies_points != 0:
            raise ValueError(
                "A-7: a listing with no explicit required technologies scores 0 in this "
                "dimension"
            )
        if self.any_of_slot_count != 1:
            raise ValueError('A-7: "X, Y, or equivalent" is exactly one any-of slot')
        if self.equivalent_may_introduce_new_technology:
            raise ValueError('A-7: "equivalent" never invents a new technology')
        if self.generic_wording_becomes_slot:
            raise ValueError("A-7: generic wording never becomes a technology slot")
        if not self.critical_unknown_when_structured_field_yields_no_technology:
            raise ValueError(
                "A-7: required technologies count as a critical unknown when a structured "
                "requirement field yields no explicit technology"
            )
        return self


class SubstitutionCredit(FrozenModel):
    """Three multipliers, and only three: direct, substitute, none.

    A peer tool in a substitutable category earns `substitute`, never `direct`. The report names
    the tool actually held, so reduced credit is a disclosure rather than a claim.
    """

    direct: float
    substitute: float
    none: float

    @model_validator(mode="after")
    def _check_order(self) -> "SubstitutionCredit":
        if self.direct != 1.0:
            raise ValueError("direct credit is the reference and must equal 1.0")
        if self.none != 0.0:
            raise ValueError("no evidence must earn exactly 0.0")
        if not 0.0 < self.substitute < self.direct:
            raise ValueError(
                "substitute credit must lie strictly between none and direct: a peer tool is "
                f"worth something and is never worth the requested tool, got {self.substitute}"
            )
        return self


class TechnologyCategory(FrozenModel):
    """One owner-approved technology category.

    `substitutable` decides everything. True means operating one member transfers to another, so
    a requirement met by a peer earns reduced credit. False means membership transfers nothing:
    a language-specific role requires that language, and a miss is a distinct red flag.

    `members` are job-side names the category recognizes. Listing a name here is not candidate
    evidence: credit still requires the candidate to hold a member in the approved dossier at a
    disclosed tier.
    """

    name: str
    substitutable: bool
    note: str
    members: tuple[str, ...]

    @model_validator(mode="after")
    def _check_category(self) -> "TechnologyCategory":
        if CANONICAL_ID_PATTERN.match(self.name) is None:
            raise ValueError(f"category name must be uppercase-snake, got {self.name!r}")
        if not self.note.strip():
            raise ValueError(f"{self.name}: a category requires a note explaining the grouping")
        if len(self.members) < 2:
            raise ValueError(
                f"{self.name}: a category needs at least two members; one member groups nothing"
            )
        if len(set(self.members)) != len(self.members):
            raise ValueError(f"{self.name}: duplicate member")
        return self


class TechnologyCategories(FrozenModel):
    """The category table and its three substitution multipliers."""

    substitution_credit: SubstitutionCredit
    categories: tuple[TechnologyCategory, ...]

    @model_validator(mode="after")
    def _check_table(self) -> "TechnologyCategories":
        names = [category.name for category in self.categories]
        if len(set(names)) != len(names):
            raise ValueError("duplicate category name")
        seen: dict[str, str] = {}
        for category in self.categories:
            for member in category.members:
                key = member.casefold()
                if key in seen:
                    raise ValueError(
                        f"{member!r} appears in both {seen[key]} and {category.name}; a "
                        "technology belongs to one category, or substitutability is ambiguous"
                    )
                seen[key] = category.name
        return self

    def category_for(self, member_key: str) -> TechnologyCategory | None:
        """Return the category whose members include this casefolded name, if any."""
        for category in self.categories:
            if member_key in {name.casefold() for name in category.members}:
                return category
        return None


class ScoringConfig(FrozenModel):
    """Weighted dimensions plus the approved P-1, P-2, P-3, P-6, and A-5 to A-7 policy."""

    weights: dict[str, int]
    evidence_tier_weighting: EvidenceTierWeights
    match_classification_thresholds: ClassificationThresholds
    seniority_bands: SeniorityBands
    report_display: ReportDisplayPolicy
    technology_base_credit_allocation: TechnologyAllocationPolicy
    technology_matching_normalization: TechnologyNormalizationPolicy
    required_vs_preferred_technology_handling: RequiredPreferredPolicy
    technology_categories: TechnologyCategories
    unresolved_policy: dict[str, Any]

    @field_validator("weights")
    @classmethod
    def _check_weights(cls, value: dict[str, int]) -> dict[str, int]:
        keys = frozenset(value)
        if keys != EXPECTED_WEIGHT_KEYS:
            missing = sorted(EXPECTED_WEIGHT_KEYS - keys)
            unexpected = sorted(keys - EXPECTED_WEIGHT_KEYS)
            raise ValueError(
                f"scoring weight keys are wrong. missing={missing} unexpected={unexpected}"
            )
        total = sum(value.values())
        if total != TOTAL_WEIGHT:
            raise ValueError(f"scoring weights must total {TOTAL_WEIGHT}, got {total}")
        return value

    @field_validator("unresolved_policy")
    @classmethod
    def _check_policy_keys(cls, value: dict[str, Any]) -> dict[str, Any]:
        expected = frozenset(REQUIRED_UNRESOLVED_POLICY_KEYS)
        keys = frozenset(value)
        if keys != expected:
            missing = sorted(expected - keys)
            unexpected = sorted(keys - expected)
            raise ValueError(
                "unresolved_policy must declare exactly the approved gate keys. "
                f"missing={missing} unexpected={unexpected}"
            )
        wrong = sorted(name for name, entry in value.items() if entry != UNRESOLVED)
        if wrong:
            raise ValueError(
                f"unresolved_policy accepts only the {UNRESOLVED!r} sentinel, got other "
                f"values for {wrong}. A key is resolved by removing it from this block and "
                "from REQUIRED_UNRESOLVED_POLICY_KEYS together, and adding a typed policy "
                "block carrying its own PolicyStatus - never by changing its value here."
            )
        return value

    def unresolved_keys(self) -> tuple[str, ...]:
        """Return gate keys still awaiting owner approval, in the approved order."""
        return tuple(
            name
            for name in REQUIRED_UNRESOLVED_POLICY_KEYS
            if self.unresolved_policy.get(name) == UNRESOLVED
        )


class SalaryTargets(FrozenModel):
    """Three salary figures: hard floor, soft minimum, market target.

    None of them blocks. A listing below the hard floor scores zero in the compensation
    dimension and is still reported with its shortfall, because a few thousand under a stated
    minimum is a judgement for a human.
    """

    hard_floor_usd: int
    soft_minimum_usd: int
    market_target_usd: int
    status: PolicyStatus
    decided_on: str
    note: str

    @model_validator(mode="after")
    def _check_order(self) -> "SalaryTargets":
        if not 0 < self.hard_floor_usd < self.soft_minimum_usd < self.market_target_usd:
            raise ValueError(
                "salary targets must ascend: hard floor below soft minimum below market "
                f"target, got {self.hard_floor_usd}, {self.soft_minimum_usd}, "
                f"{self.market_target_usd}"
            )
        if not self.decided_on.strip() or not self.note.strip():
            raise ValueError("salary targets require a decision date and a note")
        return self


class MarketReferenceRow(FrozenModel):
    """One market figure, with its source and as-of date. Both are mandatory.

    An uncited salary figure is a guess, and a guess about pay is worse than no figure.
    """

    label: str
    value: int
    as_of: str
    source: str
    note: str

    @model_validator(mode="after")
    def _check_citation(self) -> "MarketReferenceRow":
        if self.value <= 0:
            raise ValueError(f"{self.label}: a market figure must be positive")
        for field in ("as_of", "source", "note"):
            if not str(getattr(self, field)).strip():
                raise ValueError(f"{self.label}: {field} is required for a market figure")
        return self


class MarketReference(FrozenModel):
    """Published market figures used to judge whether a listing pays for the work."""

    status: PolicyStatus
    rows: tuple[MarketReferenceRow, ...]

    @model_validator(mode="after")
    def _check_rows(self) -> "MarketReference":
        labels = [row.label for row in self.rows]
        if len(set(labels)) != len(labels):
            raise ValueError("duplicate market reference label")
        return self


class RegionalPriceParity(FrozenModel):
    """Regional price parities, used only when a listing would require relocation.

    For a remote role the candidate stays put, earns the listing's salary and spends at home
    prices, so no adjustment applies. Adjusting a remote salary downward would penalise the best
    offers, which is the opposite of useful.
    """

    status: PolicyStatus
    us_average: int
    as_of: str
    source: str
    candidate_state: str
    apply_only_on_relocation: bool
    states: dict[str, float]
    note: str

    @model_validator(mode="after")
    def _check_parities(self) -> "RegionalPriceParity":
        if self.us_average != 100:
            raise ValueError("the regional price parity baseline is 100 by definition")
        if not self.apply_only_on_relocation:
            raise ValueError(
                "a remote listing must not be cost-of-living adjusted: the candidate spends at "
                "home prices, so adjusting downward would penalise the strongest offers"
            )
        if self.candidate_state not in self.states:
            raise ValueError(
                f"the candidate state {self.candidate_state!r} must have a listed parity, "
                "otherwise no comparison is possible"
            )
        for state, parity in self.states.items():
            if len(state) != 2 or not state.isupper():
                raise ValueError(f"state key must be a two-letter uppercase code, got {state!r}")
            if parity <= 0:
                raise ValueError(f"{state}: parity must be positive")
        for field in ("as_of", "source", "note"):
            if not str(getattr(self, field)).strip():
                raise ValueError(f"regional price parity requires {field}")
        return self

    def relocation_ratio(self, job_state: str) -> float | None:
        """Home parity divided by job-location parity, or None for an unlisted state.

        An unlisted state yields no adjustment rather than an interpolated guess.
        """
        target = self.states.get(job_state)
        if target is None:
            return None
        return self.states[self.candidate_state] / target


class CompensationBand(FrozenModel):
    """One compensation band. Lower bound inclusive, upper bound exclusive."""

    classification: SalaryCompatibility
    min_usd: int | None
    max_usd: int | None
    hard_blocker: bool
    points: int
    report_note: str


class CompensationConfig(FrozenModel):
    """Compensation policy (D-3, A-2, P-4). Bands tile the range with no gap or overlap."""

    currency: Literal["USD"]
    bands: tuple[CompensationBand, ...]
    contract_points: int
    unknown_points: int
    contract_handling: str
    unknown_handling: str
    salary_targets: SalaryTargets
    market_reference: MarketReference
    regional_price_parity: RegionalPriceParity

    @model_validator(mode="after")
    def _check_tiling(self) -> "CompensationConfig":
        if not self.bands:
            raise ValueError("compensation bands must not be empty")
        ordered = sorted(self.bands, key=lambda b: (b.min_usd is not None, b.min_usd or 0))
        if ordered[0].min_usd is not None:
            raise ValueError("the lowest compensation band must be open below (min_usd: null)")
        if ordered[-1].max_usd is not None:
            raise ValueError("the highest compensation band must be open above (max_usd: null)")
        for lower, upper in zip(ordered, ordered[1:], strict=False):
            if lower.max_usd != upper.min_usd:
                raise ValueError(
                    "compensation bands must tile with no gap and no overlap: "
                    f"{lower.classification} ends at {lower.max_usd} but "
                    f"{upper.classification} begins at {upper.min_usd}"
                )
        return self

    @model_validator(mode="after")
    def _check_points(self) -> "CompensationConfig":
        for value, label in (
            (self.contract_points, "contract_points"),
            (self.unknown_points, "unknown_points"),
        ):
            if value != 0:
                raise ValueError(f"{label} must be 0 under owner decision P-4, got {value}")
        ordered = sorted(self.bands, key=lambda b: (b.min_usd is not None, b.min_usd or 0))
        for band in ordered:
            if band.points < 0:
                raise ValueError(f"{band.classification}: points must not be negative")
        for lower, upper in zip(ordered, ordered[1:], strict=False):
            if lower.points > upper.points:
                raise ValueError(
                    "compensation points must not decrease as the band rises: "
                    f"{lower.classification}={lower.points} exceeds "
                    f"{upper.classification}={upper.points}"
                )
        blocking = [band for band in self.bands if band.hard_blocker]
        for band in blocking:
            if band.points != 0:
                raise ValueError(f"{band.classification}: a blocking band must score 0 points")
        return self


class BlockerRule(FrozenModel):
    """One hard blocker and whether it is enabled."""

    code: BlockerCode
    enabled: bool


class SeniorScopeRule(FrozenModel):
    """P-5 firing conditions for SENIOR_SCOPE_MATERIALLY_UNSUPPORTED.

    Both conditions are required. A senior title alone is a SENIORITY_MISMATCH concern,
    never an automatic hard blocker. This rule is NOT equivalent to P-3's 0-point
    seniority band: a role may score 0 for seniority without firing this blocker.
    """

    requires_explicit_senior_scope: bool
    minimum_unsupported_requirements: int
    senior_title_tokens: tuple[str, ...]
    unsupported_requirement_categories: tuple[str, ...]

    @model_validator(mode="after")
    def _check_rule(self) -> "SeniorScopeRule":
        if not self.requires_explicit_senior_scope:
            raise ValueError(
                "requires_explicit_senior_scope must be true: the blocker requires an "
                "explicit senior scope in addition to unsupported requirements"
            )
        if self.minimum_unsupported_requirements < MINIMUM_UNSUPPORTED_REQUIREMENTS:
            raise ValueError(
                "minimum_unsupported_requirements must be at least "
                f"{MINIMUM_UNSUPPORTED_REQUIREMENTS}: a senior title alone can never block"
            )
        if not self.senior_title_tokens:
            raise ValueError("senior_title_tokens must not be empty")
        if self.unsupported_requirement_categories != APPROVED_SENIOR_SCOPE_CATEGORIES:
            raise ValueError(
                "unsupported_requirement_categories must be the seven approved categories, "
                f"got {list(self.unsupported_requirement_categories)}"
            )
        return self


class BlockerConfig(FrozenModel):
    """Hard blocker policy (D-5, D-6, D-8, D-10, P-5)."""

    degree_equivalency_phrases: tuple[str, ...]
    blockers: tuple[BlockerRule, ...]
    senior_scope: SeniorScopeRule

    @model_validator(mode="after")
    def _check_complete(self) -> "BlockerConfig":
        codes = [rule.code for rule in self.blockers]
        if len(codes) != len(set(codes)):
            raise ValueError("duplicate blocker code in configuration")
        if set(codes) != set(BlockerCode):
            missing = sorted(c.value for c in set(BlockerCode) - set(codes))
            raise ValueError(f"blocker configuration is incomplete. missing={missing}")
        if not self.degree_equivalency_phrases:
            raise ValueError("degree_equivalency_phrases must not be empty")
        return self


class RiskFlagRule(FrozenModel):
    """One risk flag and whether it is enabled."""

    flag: RiskFlag
    enabled: bool


class RiskFlagConfig(FrozenModel):
    """Risk flag registry. Must carry every flag in PROJECT_GUARDRAILS.md."""

    flags: tuple[RiskFlagRule, ...]

    @model_validator(mode="after")
    def _check_complete(self) -> "RiskFlagConfig":
        names = [rule.flag for rule in self.flags]
        if len(names) != len(set(names)):
            raise ValueError("duplicate risk flag in configuration")
        if set(names) != set(RiskFlag):
            missing = sorted(f.value for f in set(RiskFlag) - set(names))
            raise ValueError(f"risk flag configuration is incomplete. missing={missing}")
        return self


class AssessmentConfig(FrozenModel):
    """The complete assessment policy: structurally valid, not necessarily ready to run."""

    scoring: ScoringConfig
    compensation: CompensationConfig
    blockers: BlockerConfig
    risk_flags: RiskFlagConfig

    @model_validator(mode="after")
    def _check_dimension_ceilings(self) -> "AssessmentConfig":
        weights = self.scoring.weights
        seniority_max = max(band.points for band in self.scoring.seniority_bands.bands)
        if seniority_max != weights["seniority_and_documented_evidence_compatibility"]:
            raise ValueError(
                "the highest seniority band must equal the dimension weight "
                f"({weights['seniority_and_documented_evidence_compatibility']}), "
                f"got {seniority_max}"
            )
        compensation_max = max(band.points for band in self.compensation.bands)
        if compensation_max != weights["compensation_compatibility"]:
            raise ValueError(
                "the highest compensation band must equal the dimension weight "
                f"({weights['compensation_compatibility']}), got {compensation_max}"
            )
        allocation_dimension = self.scoring.technology_base_credit_allocation.dimension
        if allocation_dimension not in weights:
            raise ValueError(
                f"the A-5 allocation dimension {allocation_dimension!r} is not a scoring "
                "dimension"
            )
        return self

    def evidence_tier_cap_points(self) -> int:
        """The point ceiling tier multipliers may reach (rule E-1)."""
        return self.scoring.weights["verified_technical_skill_alignment"]

    def unresolved_keys(self) -> tuple[str, ...]:
        """Return every policy key still awaiting owner approval, in the approved order."""
        return self.scoring.unresolved_keys()

    def require_ready(self) -> None:
        """Raise unless every policy decision needed to execute an assessment is approved."""
        unresolved = self.unresolved_keys()
        if unresolved:
            raise AssessmentPolicyUnresolvedError(unresolved)
