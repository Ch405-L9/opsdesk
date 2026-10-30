"""Technology-evidence matching (A-5, A-6, A-7).

Deterministic and pure: `(inputs, config)` in, values out. No I/O, no clock, no randomness.
Identical inputs always produce identical output.

Matching is whole-phrase equality of lookup keys. There is no token matching, substring
matching, fuzzy matching, semantic matching, embedding matching, LLM matching, or external
taxonomy or API lookup. A lookup key is derived using only the four approved A-6 steps: Unicode
NFC, casefold, whitespace collapse, trim.

One further route exists, added by owner decision on 2026-09-26: an owner-approved technology
category. Where a category is marked substitutable, holding a peer member earns reduced credit
and the match names the tool actually held, never the one requested; the gap is raised as well,
so reduced credit can never be read as the requested tool. Where a category is marked
non-substitutable, such as a programming language, a peer earns nothing and raises
CORE_LANGUAGE_GAP. Category membership is still whole-phrase: nothing is inferred, and credit
requires the candidate to hold a member in the approved dossier at a disclosed tier.

Every match carries the nine audit values `TechnologyMatch` requires, so an undisclosed match
is unconstructable (E-5). Best tier wins (E-3). A required technology with no evidence scores
zero and raises a gap (E-4); one supported only at Tier 2 or Tier 4 receives partial credit
and still raises a gap (E-7).

Preferred technologies are not accepted here at all: required technologies are the only input
to the dimension (A-7), and preferred extraction is deferred.
"""

import unicodedata

from vetted.core.config.schema import TechnologyCategories, TechnologyNormalizationPolicy
from vetted.core.domain.assessment import (
    PARTIAL_CREDIT_TIERS,
    TechnologyGap,
    TechnologyMatch,
)
from vetted.core.dossier.terms import CandidateTerm
from vetted.core.enums import EvidenceTier, MatchMethod, RequirementKind, TechnologyGapReason

__all__ = [
    "REQUIRED_SLOT_TIER_ORDER",
    "lookup_key",
    "match_technologies",
    "resolve_job_phrase",
]

REQUIRED_SLOT_TIER_ORDER: tuple[EvidenceTier, ...] = (
    EvidenceTier.TIER_1_VERIFIED_SKILL,
    EvidenceTier.TIER_3_EMPLOYMENT_EVIDENCE,
    EvidenceTier.TIER_2_PROJECT_EVIDENCE,
    EvidenceTier.TIER_4_TRAINING,
)
"""Best-to-worst tier order (E-3), taken from the approved P-1 multipliers.

Tier ordinal deliberately does not track weight: Tier 3 (0.90) outranks Tier 2 (0.70), per
rule E-8. Nothing here may sort by tier name or ordinal.
"""


def lookup_key(value: str) -> str:
    """Derive a lookup key using only the four approved A-6 steps, in order.

    NFC, casefold, whitespace collapse, trim. No punctuation stripping, no version stripping,
    and no acronym expansion: every such variant is an explicit alias row instead.
    """
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _display_names(
    normalization: TechnologyNormalizationPolicy,
) -> dict[str, str]:
    """Return canonical identifier -> its single approved display name.

    Human-facing output uses the display name, never the identifier and never the listing's own
    spelling. A job asking for "React.js" is reported as React.
    """
    return {entry.id: entry.display_name for entry in normalization.canonical_technologies}


def _registry(
    normalization: TechnologyNormalizationPolicy,
) -> tuple[dict[str, str], dict[str, str]]:
    """Return (key -> canonical id) for display names, and (key -> alias family id).

    Both the job side and the candidate side resolve through this same one-way table, which
    gives symmetric matching without bidirectional edges (A-6).
    """
    display: dict[str, str] = {
        lookup_key(entry.display_name): entry.id
        for entry in normalization.canonical_technologies
    }
    alias: dict[str, str] = {}
    for family in normalization.alias_families:
        for variant in family.variants:
            alias[lookup_key(variant)] = family.canonical_id
    return display, alias


def resolve_job_phrase(
    phrase: str,
    normalization: TechnologyNormalizationPolicy,
) -> tuple[str, MatchMethod, str | None]:
    """Resolve one phrase to (identifier, method, alias family), by whole-phrase equality.

    An approved canonical display name resolves EXACT to its identifier. An approved alias
    variant resolves ALIAS to its family's identifier. Any other phrase resolves EXACT to its
    own lookup key: the approved registry covers only the technologies that needed a variant
    row, so a technology with no variants still matches itself. Such an identifier is the
    lowercase lookup key rather than an approved uppercase identifier, which is how a report
    can tell the two apart.

    Nothing is ever guessed. An unapproved alias never matches, and a phrase that reaches no
    candidate evidence simply finds none.
    """
    key = lookup_key(phrase)
    display, alias = _registry(normalization)
    if key in display:
        return display[key], MatchMethod.EXACT, None
    if key in alias:
        return alias[key], MatchMethod.ALIAS, alias[key]
    return key, MatchMethod.EXACT, None


def _candidate_index(
    normalization: TechnologyNormalizationPolicy,
    terms: tuple[CandidateTerm, ...],
) -> dict[str, list[CandidateTerm]]:
    """Group candidate terms by the identifier they resolve to through the same table."""
    index: dict[str, list[CandidateTerm]] = {}
    for entry in terms:
        identifier, _, _ = resolve_job_phrase(entry.term, normalization)
        index.setdefault(identifier, []).append(entry)
    return index


def _best(candidates: list[CandidateTerm]) -> CandidateTerm:
    """Return the highest-weighted evidence for a slot (E-3), never the first or the newest."""
    return min(candidates, key=lambda entry: REQUIRED_SLOT_TIER_ORDER.index(entry.tier))


def _substitute(
    phrase: str,
    categories: TechnologyCategories | None,
    terms: tuple[CandidateTerm, ...],
) -> tuple[CandidateTerm, str, bool] | None:
    """Find a peer tool the candidate holds in the same owner-approved category.

    Returns the best peer, the category name, and whether that category is substitutable.
    A non-substitutable category still reports its peer, because "you know Python, they want
    Rust" is a more useful statement than "no evidence" - it just earns no credit.
    """
    if categories is None:
        return None
    category = categories.category_for(lookup_key(phrase))
    if category is None:
        return None
    member_keys = {lookup_key(name) for name in category.members}
    peers = [entry for entry in terms if lookup_key(entry.term) in member_keys]
    if not peers:
        return None
    return _best(peers), category.name, category.substitutable


def match_technologies(
    required_technologies: tuple[str, ...],
    terms: tuple[CandidateTerm, ...],
    normalization: TechnologyNormalizationPolicy,
    categories: TechnologyCategories | None = None,
) -> tuple[tuple[TechnologyMatch, ...], tuple[TechnologyGap, ...]]:
    """Match required technologies to candidate evidence, with tier and audit trail.

    Returns matched slots and unsatisfied slots. Required slots are deduplicated by resolved
    identifier, so a listing repeating a technology yields one slot. Any-of grouping is not
    applied: the capture format carries no any-of marker, so each entry is one slot until a
    grouped requirement source exists.

    `terms` is the candidate evidence index, normally
    `vetted.core.dossier.candidate_terms(dossier)`. It is passed rather than fetched
    so the dependency is explicit and so synthetic terms can be supplied in tests. A listing
    can never modify it.
    """
    index = _candidate_index(normalization, terms)
    display, _ = _registry(normalization)
    approved_identifiers = set(display.values())
    display_names = _display_names(normalization)

    matches: list[TechnologyMatch] = []
    gaps: list[TechnologyGap] = []
    seen: set[str] = set()

    for phrase in required_technologies:
        if not phrase.strip():
            continue
        identifier, method, family = resolve_job_phrase(phrase, normalization)
        if identifier in seen:
            continue
        seen.add(identifier)

        evidence = index.get(identifier)
        if evidence is None:
            peer = _substitute(phrase, categories, terms)
            if peer is not None:
                best_peer, category_name, substitutable = peer
                if substitutable:
                    matches.append(
                        TechnologyMatch(
                            technology=best_peer.term,
                            raw_job_phrase=phrase,
                            normalized_job_identifier=identifier,
                            raw_candidate_evidence_phrase=best_peer.term,
                            normalized_candidate_identifier=lookup_key(best_peer.term),
                            match_method=MatchMethod.CATEGORY_SUBSTITUTE,
                            alias_family_identifier=category_name,
                            requirement_kind=RequirementKind.REQUIRED,
                            tier=best_peer.tier,
                            evidence_reference=best_peer.evidence_reference,
                        )
                    )
                gaps.append(
                    TechnologyGap(
                        raw_job_phrase=phrase,
                        normalized_job_identifier=None,
                        reason=(
                            TechnologyGapReason.CATEGORY_SUBSTITUTE_ONLY
                            if substitutable
                            else TechnologyGapReason.CORE_LANGUAGE_GAP
                        ),
                        best_tier_found=best_peer.tier,
                    )
                )
                continue
            gaps.append(
                TechnologyGap(
                    raw_job_phrase=phrase,
                    normalized_job_identifier=(
                        identifier if identifier in approved_identifiers else None
                    ),
                    reason=(
                        TechnologyGapReason.NO_EVIDENCE
                        if identifier in approved_identifiers
                        else TechnologyGapReason.UNRECOGNIZED_TERM
                    ),
                    best_tier_found=None,
                )
            )
            continue

        best = _best(evidence)
        matches.append(
            TechnologyMatch(
                technology=display_names.get(identifier, phrase.strip()),
                raw_job_phrase=phrase,
                normalized_job_identifier=identifier,
                raw_candidate_evidence_phrase=best.term,
                normalized_candidate_identifier=identifier,
                match_method=method,
                alias_family_identifier=family,
                requirement_kind=RequirementKind.REQUIRED,
                tier=best.tier,
                evidence_reference=best.evidence_reference,
            )
        )
        if best.tier in PARTIAL_CREDIT_TIERS:
            gaps.append(
                TechnologyGap(
                    raw_job_phrase=phrase,
                    normalized_job_identifier=identifier,
                    reason=TechnologyGapReason.TIER_2_OR_TIER_4_ONLY,
                    best_tier_found=best.tier,
                )
            )

    return tuple(matches), tuple(gaps)
