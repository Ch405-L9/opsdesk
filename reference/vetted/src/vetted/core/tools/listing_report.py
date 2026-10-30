"""Rank several captured listings side by side.

Reads one or more captures from standard input, separated by a line containing only `===`, and
prints a short ranked list: title, company, link, technology points, salary position, and the
first gap. Then the per-listing detail.

Writes no file, makes no network call, and takes no external action. Not a CLI command: the
Typer CLI stays `doctor`-only while `report_and_cli_score_display_scope` is unresolved.

Only one of nine dimensions is scored, so the ranking is by technology alignment, and it says so.
No match score, classification, or recommendation is produced.

Usage:

    cat capture1.md sep.md capture2.md | PYTHONPATH=src python -m vetted.core.tools.listing_report

where `sep.md` is a file containing only `===`. Or paste captures separated by that line.
"""

import re
import sys

from vetted.core.assess.scoring import score_technology_alignment
from vetted.core.config.loader import load_assessment_config
from vetted.core.config.schema import AssessmentConfig, RegionalPriceParity, SalaryTargets
from vetted.core.domain import UNKNOWN
from vetted.core.domain.assessment import TechnologyAlignmentResult
from vetted.core.domain.job import NormalizedJob
from vetted.core.dossier import candidate_terms, load_dossier
from vetted.core.enums import RelocationStatus, TechnologyGapReason, WorkArrangementType
from vetted.core.ingest.capture import CaptureFormatError, parse_capture

__all__ = ["SEPARATOR", "main", "salary_position", "split_captures"]

SEPARATOR = "==="

STATE_AFTER_COMMA = re.compile(r",\s*([A-Z]{2})\b")
"""A state code in the standard "City, ST" position. Nothing else is read as a state."""

RELOCATION_ARRANGEMENTS = frozenset(
    {WorkArrangementType.ON_SITE, WorkArrangementType.HYBRID}
)
"""Only these can require moving. A remote role is spent at home prices, so no adjustment."""

USAGE = (
    "vetted listing-report\n"
    "\n"
    "Ranks several captured listings by technology alignment.\n"
    "Reads captures from standard input, separated by a line containing only ===\n"
    "\n"
    "  cat a.md sep.md b.md | PYTHONPATH=src python -m vetted.core.tools.listing_report\n"
    "\n"
    "One of nine dimensions is scored, so this ranks on technology alignment alone. It is not\n"
    "a match score, not a classification, and not a recommendation. Nothing is written and\n"
    "nothing leaves this machine.\n"
)


def split_captures(text: str) -> list[str]:
    """Split standard input into capture blocks on a line containing only the separator."""
    blocks: list[list[str]] = [[]]
    for line in text.splitlines():
        if line.strip() == SEPARATOR:
            blocks.append([])
            continue
        blocks[-1].append(line)
    return ["\n".join(block).strip() for block in blocks if "\n".join(block).strip()]


def _state_code(location_text: str, known: dict[str, float]) -> str | None:
    """Return a state code written in the standard "City, ST" position.

    The code must directly follow a comma. Matching any uppercase token would read "travel OK"
    as Oklahoma, and once IN, OR and ME are listed it would read "in", "or" and "me" as Indiana,
    Oregon and Maine. Requiring the comma position follows how locations are actually written and
    needs no word list.

    No state-name lookup and no inference. An unrecognized or ambiguous location yields no
    adjustment, which the output states.
    """
    found = sorted({code for code in STATE_AFTER_COMMA.findall(location_text)} & set(known))
    return found[0] if len(found) == 1 else None


def salary_position(
    job: NormalizedJob,
    targets: SalaryTargets,
    parity: RegionalPriceParity,
) -> str:
    """Describe where a listing's stated pay sits, against the floor and the market.

    Cost of living is applied only when the listing could require relocation. For a remote role
    the candidate stays put and spends at home prices, so the listed figure stands.

    The range is displayed when the listing states one, and the judgement is made on the
    minimum, which is the approved conservative rule. A listing whose top end clears the market
    target still shows its full range, so a high-end offer is never hidden behind its floor.
    """
    stated = job.compensation.base_salary_min_usd
    if stated == UNKNOWN:
        return "salary not stated — missing evidence, never a rejection"

    top = job.compensation.base_salary_max_usd
    shown = f"{stated:,}" if top == UNKNOWN else f"{stated:,}-{top:,}"
    effective = float(stated)
    note = ""
    relocating = (
        job.work.work_arrangement in RELOCATION_ARRANGEMENTS
        or job.work.relocation_status is RelocationStatus.REQUIRED
    )
    if relocating and job.work.location_text != UNKNOWN:
        code = _state_code(str(job.work.location_text), parity.states)
        ratio = parity.relocation_ratio(code) if code else None
        if ratio is not None:
            effective = float(stated) * ratio
            note = (
                f" [{code} cost of living, {parity.candidate_state} equivalent "
                f"{effective:,.0f}]"
            )
        else:
            note = " [relocation possible, no published parity for this location]"

    if effective >= targets.market_target_usd:
        verdict = f"at or above market target {targets.market_target_usd:,}"
    elif effective >= targets.soft_minimum_usd:
        short = targets.market_target_usd - effective
        verdict = f"above your minimum, {short:,.0f} under market target"
    elif effective >= targets.hard_floor_usd:
        short = targets.soft_minimum_usd - effective
        verdict = f"{short:,.0f} under your soft minimum — your call"
    else:
        verdict = f"below your {targets.hard_floor_usd:,} floor — shown, not dropped"
    return f"{shown} stated. {verdict}{note}"


def _headline_gap(result: TechnologyAlignmentResult) -> str:
    if not result.gaps:
        return "no gaps"
    priority = (
        TechnologyGapReason.CORE_LANGUAGE_GAP,
        TechnologyGapReason.PROHIBITED_INFERENCE,
        TechnologyGapReason.UNRECOGNIZED_TERM,
        TechnologyGapReason.NO_EVIDENCE,
        TechnologyGapReason.CATEGORY_SUBSTITUTE_ONLY,
        TechnologyGapReason.TIER_2_OR_TIER_4_ONLY,
    )
    worst = min(result.gaps, key=lambda gap: priority.index(gap.reason))
    return f"{worst.raw_job_phrase} ({worst.reason.value})"


def _render(
    scored: list[tuple[NormalizedJob, TechnologyAlignmentResult]],
    config: AssessmentConfig,
) -> str:
    targets = config.compensation.salary_targets
    parity = config.compensation.regional_price_parity
    lines = [
        "Vetted — listing comparison",
        "",
        f"{len(scored)} listing(s). Ranked by technology alignment, which is one of nine",
        "dimensions. This is not a match score, classification, or recommendation.",
        "",
    ]
    ordered = sorted(scored, key=lambda pair: pair[1].points, reverse=True)
    for rank, (job, result) in enumerate(ordered, start=1):
        url = job.provenance.source_url
        lines.append(f"{rank}. {job.job_title} — {job.company.company_name}")
        lines.append(f"     link          {url if url != UNKNOWN else 'not captured'}")
        lines.append(
            f"     tech           {result.points!r} of {result.dimension_weight}"
            f"  ({result.required_slot_count} required slot(s))"
        )
        lines.append(f"     salary         {salary_position(job, targets, parity)}")
        lines.append(f"     top gap        {_headline_gap(result)}")
        lines.append(
            f"     arrangement    {job.work.work_arrangement.value}, "
            f"{job.work.employment_type.value}, relocation "
            f"{job.work.relocation_status.value}"
        )
        lines.append("")

    lines.append("Detail")
    lines.append("")
    for rank, (job, result) in enumerate(ordered, start=1):
        lines.append(f"{rank}. {job.job_title} — {job.company.company_name}")
        for match in result.matches:
            substitute = match.match_method.value == "CATEGORY_SUBSTITUTE"
            label = (
                f"category substitute via {match.alias_family_identifier}: you hold "
                f"{match.technology}, they asked for {match.raw_job_phrase}"
                if substitute
                else f"{match.technology} ({match.match_method.value})"
            )
            lines.append(f"     match  {label} — {match.tier.value}")
            lines.append(f"            evidence: {match.evidence_reference}")
        for gap in result.gaps:
            lines.append(f"     gap    {gap.raw_job_phrase!r} — {gap.reason.value}")
        if not result.matches and not result.gaps:
            lines.append("     no required technologies captured")
        lines.append("")

    lines.append(
        "Eight dimensions have no allocation rule yet, so nothing above is a verdict. Read the"
    )
    lines.append("gaps before the numbers.")
    return "\n".join(lines)


def report_from_text(text: str) -> str:
    """Rank every capture in `text` against the user's dossier and return the report text."""
    blocks = split_captures(text)
    if not blocks:
        return "No captures found.\n"

    config = load_assessment_config()
    dossier, explicit = load_dossier()
    terms = candidate_terms(dossier, explicit)
    scored: list[tuple[NormalizedJob, TechnologyAlignmentResult]] = []
    problems: list[str] = []
    for index, block in enumerate(blocks, start=1):
        try:
            job = parse_capture(block, f"capture-{index}")
        except CaptureFormatError as error:
            problems.append(f"  capture {index}: {error}")
            continue
        scored.append(
            (job, score_technology_alignment(job.job_id, job.required_technologies, terms, config))
        )

    out: list[str] = []
    if problems:
        out.append("Some captures could not be imported.\n\n")
        out.append("\n".join(problems) + "\n\n")
    if scored:
        out.append(_render(scored, config) + "\n")
    return "".join(out)


def main() -> int:
    """Read captures from stdin, print the ranked comparison, and return an exit code."""
    if sys.stdin.isatty():
        sys.stdout.write(USAGE)
        return 0
    text = sys.stdin.read()
    if not split_captures(text):
        sys.stdout.write("No captures found on standard input.\n")
        return 0
    sys.stdout.write(report_from_text(text).replace("capture-", "stdin-"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
