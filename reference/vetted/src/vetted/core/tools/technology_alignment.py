"""Score one listing's required technologies against the approved dossier.

Reads one required technology per line from standard input and prints the
`verified_technical_skill_alignment` dimension. Writes no file, reads no file other than
`config/*.yaml` through the configuration loader, makes no network call, and takes no external
action.

This is not a CLI command and not a report. The Typer CLI stays `doctor`-only while
`report_and_cli_score_display_scope` is unresolved. What is printed here is one dimension of
nine, never a match score, never a classification, and never a recommendation.

Output order follows P-6 and rule C-5: provenance, the evidence-tier map, then gaps, and the
points last. The score never appears in the first line or in any heading.

No capture file is parsed. Splitting a capture's `required_technologies` block would be a new
delimiter rule, and A-6 forbids punctuation stripping, so a pasted line keeping its bullet or
trailing comma will not match. Gaps print their raw phrase with `repr()` so such artifacts are
visible rather than mysterious.

Usage:

    printf 'Python\\nRAG\\nReact.js\\n' \\
        | PYTHONPATH=src python -m vetted.core.tools.technology_alignment
"""

import sys

from vetted.core.assess.scoring import score_technology_alignment
from vetted.core.config.loader import load_assessment_config
from vetted.core.config.schema import REQUIRED_UNRESOLVED_POLICY_KEYS
from vetted.core.domain.assessment import GAP_FLAG, TechnologyAlignmentResult
from vetted.core.dossier import candidate_terms, load_dossier
from vetted.core.enums import TechnologyGapReason

__all__ = ["format_result", "main", "read_required_technologies"]

USAGE = (
    "vetted technology-alignment\n"
    "\n"
    "Scores the verified_technical_skill_alignment dimension for one listing.\n"
    "Reads one required technology per line from standard input.\n"
    "\n"
    "  printf 'Python\\nRAG\\nReact.js\\n' \\\n"
    "    | PYTHONPATH=src python -m vetted.core.tools.technology_alignment\n"
    "\n"
    "Paste clean lines. A leading bullet, a trailing comma, or a stray character is part of\n"
    "the phrase: normalization applies only Unicode NFC, casefolding, whitespace collapse,\n"
    "and trim, so decorated lines will not match.\n"
    "\n"
    "This prints one dimension of nine. It is not a match score, not a classification, and\n"
    "not a recommendation. Nothing is written and nothing leaves this machine.\n"
)


def read_required_technologies(text: str) -> tuple[str, ...]:
    """Split stdin into required technology phrases, one per line.

    Blank lines are dropped. Nothing else is altered: no bullet is stripped, no punctuation is
    removed, and no line is split on a comma, because A-6 permits only the four normalization
    steps and those belong to the matcher.
    """
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def format_result(result: TechnologyAlignmentResult, source: str, version: str) -> str:
    """Render the dimension for a human. Points come last and are never abbreviated."""
    lines: list[str] = [
        "Vetted — verified_technical_skill_alignment",
        "",
        "One dimension of nine. Not a match score, classification, or recommendation.",
        f"Candidate evidence: {source}, version {version}, read-only.",
        f"Listing: {result.job_id}",
        "",
        f"Required technology slots after normalization and deduplication: "
        f"{result.required_slot_count}",
        "",
    ]

    lines.append("Evidence-tier map")
    if result.matches:
        for match in result.matches:
            lines.append(f"  {match.technology}")
            lines.append(f"    listing said        {match.raw_job_phrase!r}")
            lines.append(f"    matched             {match.raw_candidate_evidence_phrase!r}")
            lines.append(f"    identifier          {match.normalized_job_identifier}")
            lines.append(
                f"    method              {match.match_method.value}"
                + (
                    f", alias family {match.alias_family_identifier}"
                    if match.alias_family_identifier is not None
                    else ""
                )
            )
            lines.append(f"    tier                {match.tier.value}")
            lines.append(f"    evidence            {match.evidence_reference}")
    else:
        lines.append("  No required technology matched candidate evidence.")
    lines.append("")

    lines.append("Gaps")
    if result.gaps:
        for gap in result.gaps:
            detail = (
                f"best evidence found {gap.best_tier_found.value}"
                if gap.best_tier_found is not None
                else "no candidate evidence at any tier"
            )
            lines.append(
                f"  {gap.raw_job_phrase!r} — {gap.reason.value} — {detail} — "
                f"raises {GAP_FLAG.value}"
            )
        unrecognized = [
            gap.raw_job_phrase
            for gap in result.gaps
            if gap.reason is TechnologyGapReason.UNRECOGNIZED_TERM
        ]
        if unrecognized:
            lines.append("")
            lines.append("  Unrecognized terms, for owner review. Each remained a required")
            lines.append("  slot, scored zero, and stayed in the denominator. Approving an")
            lines.append("  alias later affects future runs only.")
            for phrase in unrecognized:
                lines.append(f"    {phrase!r}")
    else:
        lines.append("  None.")
    lines.append("")

    lines.append("Dimension points — 1 of 9 dimensions — exact and unrounded — not a match score")
    lines.append(
        f"  {result.dimension_weight} × {result.multiplier_sum!r} / "
        f"{result.required_slot_count} = {result.points!r}"
        if result.required_slot_count
        else f"  no required technology slots, so {result.points!r} of "
        f"{result.dimension_weight} by policy"
    )
    lines.append(f"  of a possible {result.dimension_weight}")
    lines.append("")

    lines.append("Human next action")
    if result.required_slot_count == 0:
        lines.append("  This listing names no required technology. Zero here reflects absent")
        lines.append("  listing information, not candidate unsuitability, and can never on its")
        lines.append("  own produce AVOID or DO_NOT_APPLY.")
    elif result.gaps:
        lines.append("  Read the gaps before the number. A gap is an honest statement of what")
        lines.append("  the evidence does not support; do not present a gapped technology as")
        lines.append("  experience.")
    else:
        lines.append("  Every required technology is supported by disclosed evidence. The other")
        lines.append("  eight dimensions are not implemented, so no overall judgement follows.")
    lines.append("")
    lines.append(
        f"Eight dimensions and {len(REQUIRED_UNRESOLVED_POLICY_KEYS)} policy keys remain "
        "unresolved. No total score exists."
    )
    return "\n".join(lines)


def main() -> int:
    """Read stdin, print the dimension, and return an exit code. Always returns 0."""
    if sys.stdin.isatty():
        sys.stdout.write(USAGE)
        return 0

    required = read_required_technologies(sys.stdin.read())
    dossier, explicit = load_dossier()
    config = load_assessment_config()
    result = score_technology_alignment(
        "stdin", required, candidate_terms(dossier, explicit), config
    )
    sys.stdout.write(
        format_result(result, "your approved dossier", "user-approved") + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
