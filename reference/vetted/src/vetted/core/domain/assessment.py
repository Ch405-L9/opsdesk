"""Assessment result models.

`TechnologyMatch.tier` has no default, so an untiered technology match cannot be constructed
(D-7). Reports must disclose the tier behind every match.

`Assessment.score` is optional and unset: no scoring logic exists, and the remaining five
policy keys still gate readiness.

`TechnologyMatch` carries the nine values the A-6 audit rule requires, each mandatory, so an
undisclosed match is unconstructable (E-5). `TechnologyGap` records an unsatisfied required
slot and its reason (E-4, E-6, E-7). `TechnologyAlignmentResult` is the dimension-result type
permitted while the readiness gate stands: it deliberately carries no total score, no
`MatchClassification`, no `Recommendation`, and no `ValidationStatus`, so the dimension path
cannot produce a full assessment. `Assessment` remains reachable only through the gated
`assess_job`.

`MatchMethod`, `RequirementKind`, and `TechnologyGapReason` are defined in `vetted.core.enums`,
the single enum definition site, and imported here.
"""

from typing import Final, Literal

from pydantic import model_validator

from vetted.core.domain import FrozenModel
from vetted.core.enums import (
    BlockerCode,
    EvidenceTier,
    MatchClassification,
    MatchMethod,
    Recommendation,
    RequirementKind,
    RiskFlag,
    SalaryCompatibility,
    TechnologyGapReason,
    ValidationStatus,
)

__all__ = [
    "GAP_FLAG",
    "PARTIAL_CREDIT_TIERS",
    "Assessment",
    "BlockerFinding",
    "CompensationAssessment",
    "RiskFlagFinding",
    "TechnologyAlignmentResult",
    "TechnologyGap",
    "TechnologyMatch",
]

GAP_FLAG: Final = RiskFlag.REQUIRED_SKILL_GAP
"""The only risk flag a technology gap may raise. A-5 through A-7 invent no new flag."""

PARTIAL_CREDIT_TIERS: Final[frozenset[EvidenceTier]] = frozenset(
    {EvidenceTier.TIER_2_PROJECT_EVIDENCE, EvidenceTier.TIER_4_TRAINING}
)
"""E-7: a required technology supported only by these tiers still raises the gap."""

NO_EVIDENCE_REASONS: Final[frozenset[TechnologyGapReason]] = frozenset(
    {TechnologyGapReason.NO_EVIDENCE, TechnologyGapReason.UNRECOGNIZED_TERM}
)
"""E-4: these reasons mean no candidate evidence was found at any tier."""


class TechnologyMatch(FrozenModel):
    """A listing technology matched to candidate evidence, with its full audit trail.

    Every field is mandatory, so a match that cannot be fully disclosed cannot be constructed
    (E-5). `tier` in particular has no default: no tier may create an unverified skill (D-7).

    `technology` is the approved display name shown to a human; `normalized_job_identifier`
    is the internal canonical identifier and is never displayed alone (A-6).

    For a CATEGORY_SUBSTITUTE match, `technology` is the tool the candidate actually holds, not
    the one the listing asked for, and `alias_family_identifier` carries the category name rather
    than an alias family. The field name is imprecise for that case and is worth renaming once
    the category lane settles; the report always states which tool was held either way, so
    nothing claims the requested tool.
    """

    technology: str
    raw_job_phrase: str
    normalized_job_identifier: str
    raw_candidate_evidence_phrase: str
    normalized_candidate_identifier: str
    match_method: MatchMethod
    alias_family_identifier: str | None
    requirement_kind: RequirementKind
    tier: EvidenceTier
    evidence_reference: str

    @model_validator(mode="after")
    def _check_disclosure(self) -> "TechnologyMatch":
        for name in (
            "technology",
            "raw_job_phrase",
            "normalized_job_identifier",
            "raw_candidate_evidence_phrase",
            "normalized_candidate_identifier",
            "evidence_reference",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be blank: every match is fully disclosed")
        return self

    @model_validator(mode="after")
    def _check_match_method(self) -> "TechnologyMatch":
        needs_source = {MatchMethod.ALIAS, MatchMethod.CATEGORY_SUBSTITUTE}
        if self.match_method in needs_source:
            if self.alias_family_identifier is None or not (
                self.alias_family_identifier.strip()
            ):
                raise ValueError(
                    f"a {self.match_method.value} match must name what produced it: the alias "
                    "family for ALIAS, the category for CATEGORY_SUBSTITUTE"
                )
        elif self.alias_family_identifier is not None:
            raise ValueError(
                "an EXACT match has no alias family; alias_family_identifier must be None"
            )
        return self


class TechnologyGap(FrozenModel):
    """A required technology slot that candidate evidence does not satisfy.

    Only a required slot can produce a gap: `requirement_kind` is fixed to `"REQUIRED"`,
    because preferred technologies never raise a gap (A-7).

    Every gap maps to `GAP_FLAG`, that is `RiskFlag.REQUIRED_SKILL_GAP`, and to no other
    flag. A-5 through A-7 create no new `RiskFlag` member.

    `normalized_job_identifier` is `None` when the phrase is unrecognized: an unrecognized
    required phrase remains a slot, scores zero, stays in the denominator, and raises the
    gap (A-6).
    """

    raw_job_phrase: str
    normalized_job_identifier: str | None
    requirement_kind: Literal[RequirementKind.REQUIRED] = RequirementKind.REQUIRED
    reason: TechnologyGapReason
    best_tier_found: EvidenceTier | None

    @model_validator(mode="after")
    def _check_reason(self) -> "TechnologyGap":
        if not self.raw_job_phrase.strip():
            raise ValueError("raw_job_phrase must not be blank")
        if (
            self.reason is TechnologyGapReason.UNRECOGNIZED_TERM
            and self.normalized_job_identifier is not None
        ):
            raise ValueError("an unrecognized term has no normalized identifier (A-6)")
        if self.reason in NO_EVIDENCE_REASONS:
            if self.best_tier_found is not None:
                raise ValueError(f"{self.reason} means no evidence was found (E-4)")
        elif self.best_tier_found is None:
            raise ValueError(f"{self.reason} requires the tier that was found")
        if (
            self.reason is TechnologyGapReason.TIER_2_OR_TIER_4_ONLY
            and self.best_tier_found not in PARTIAL_CREDIT_TIERS
        ):
            raise ValueError(
                "TIER_2_OR_TIER_4_ONLY applies only to Tier 2 or Tier 4 evidence (E-7)"
            )
        return self


class TechnologyAlignmentResult(FrozenModel):
    """The `verified_technical_skill_alignment` dimension result, and nothing more.

    This is the dimension-result type permitted while the five remaining policy keys gate
    readiness. It deliberately carries no total score, no `MatchClassification`, no
    `Recommendation`, and no `ValidationStatus`, so no code path can turn a dimension figure
    into a full assessment. `Assessment` stays reachable only through `assess_job`, which
    requires `load_ready_assessment_config`.

    `points` is exact and unrounded: rounding remains the unresolved `score_rounding_rule`
    (A-5). Preferred technologies appear nowhere here - they enter neither the numerator nor
    the denominator, and preferred extraction is deferred (A-7).
    """

    job_id: str
    dimension: Literal["verified_technical_skill_alignment"]
    dimension_weight: int
    required_slot_count: int
    multiplier_sum: float
    points: float
    matches: tuple[TechnologyMatch, ...] = ()
    gaps: tuple[TechnologyGap, ...] = ()

    @model_validator(mode="after")
    def _check_result(self) -> "TechnologyAlignmentResult":
        if not self.job_id.strip():
            raise ValueError("job_id must not be blank")
        if self.dimension_weight <= 0:
            raise ValueError("dimension_weight must be positive")
        if self.required_slot_count < 0:
            raise ValueError("required_slot_count must not be negative")
        if self.multiplier_sum < 0:
            raise ValueError("multiplier_sum must not be negative")
        if not 0 <= self.points <= self.dimension_weight:
            raise ValueError(
                f"points must lie in [0, {self.dimension_weight}] (E-1), got {self.points}"
            )
        if self.required_slot_count == 0:
            if self.multiplier_sum != 0 or self.points != 0:
                raise ValueError("zero required slots scores exactly 0 points (A-5)")
            if self.gaps:
                raise ValueError("zero required slots raises no gap: nothing was required")
        if self.multiplier_sum > self.required_slot_count:
            raise ValueError(
                "multiplier_sum cannot exceed the slot count: no multiplier exceeds 1.00"
            )
        if any(
            match.requirement_kind is not RequirementKind.REQUIRED for match in self.matches
        ):
            raise ValueError(
                "only required technologies enter this dimension (A-7); a preferred match "
                "may not appear here"
            )
        return self


class BlockerFinding(FrozenModel):
    """A hard blocker. Cannot be suppressed by any score."""

    code: BlockerCode
    rationale: str


class RiskFlagFinding(FrozenModel):
    """A raised risk flag and the reason it was raised."""

    flag: RiskFlag
    rationale: str


class CompensationAssessment(FrozenModel):
    """Compensation band outcome and the note a report must display."""

    classification: SalaryCompatibility
    report_note: str


class Assessment(FrozenModel):
    """A complete human-review assessment.

    Blockers are rendered before the score and are never hidden by one. No recommendation
    means "apply automatically".
    """

    job_id: str
    validation_status: ValidationStatus
    classification: MatchClassification
    recommendation: Recommendation
    blockers: tuple[BlockerFinding, ...] = ()
    risk_flags: tuple[RiskFlagFinding, ...] = ()
    technology_matches: tuple[TechnologyMatch, ...] = ()
    skill_gaps: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    compensation: CompensationAssessment | None = None
    score: int | None = None
