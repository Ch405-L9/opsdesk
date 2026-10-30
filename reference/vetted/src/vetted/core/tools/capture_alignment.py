"""Score a captured listing's required technologies against the approved dossier.

Reads a complete job capture, in `JOB_CAPTURE_TEMPLATE.md` format, from standard input, imports
it into a `NormalizedJob`, and prints the `verified_technical_skill_alignment` dimension.

Writes no file, reads no file other than `config/*.yaml` through the configuration loader, makes
no network call, and takes no external action. The capture never touches disk through this tool:
it arrives on standard input, so no path is accepted and no captures directory is created.

Not a CLI command. The Typer CLI stays `doctor`-only while
`report_and_cli_score_display_scope` is unresolved. One dimension of nine is printed, never a
match score, classification, or recommendation.

Eight of the nine dimensions have no allocation rule yet, so the fields this importer now
populates - work arrangement, relocation status, employment type, company URLs - are read and
disclosed but not scored.

Usage:

    PYTHONPATH=src python -m vetted.core.tools.capture_alignment < capture.md
"""

import sys

from vetted.core.assess.scoring import score_technology_alignment
from vetted.core.config.loader import load_assessment_config
from vetted.core.domain.job import NormalizedJob
from vetted.core.dossier import candidate_terms, load_dossier
from vetted.core.ingest.capture import CaptureFormatError, parse_capture
from vetted.core.tools.technology_alignment import format_result

__all__ = ["format_capture_facts", "main"]

USAGE = (
    "vetted capture-alignment\n"
    "\n"
    "Scores the verified_technical_skill_alignment dimension for one captured listing.\n"
    "Reads a complete capture, in JOB_CAPTURE_TEMPLATE.md format, from standard input.\n"
    "\n"
    "  PYTHONPATH=src python -m vetted.core.tools.capture_alignment < capture.md\n"
    "\n"
    "required_technologies is read one per line. A comma-separated line arrives as a single\n"
    "phrase and will not match, because splitting on a comma is not an approved rule.\n"
    "\n"
    "Absent fields become UNKNOWN. A malformed salary or an unrecognized enum value stops the\n"
    "import rather than being guessed.\n"
    "\n"
    "This prints one dimension of nine. It is not a match score, not a classification, and\n"
    "not a recommendation. Nothing is written and nothing leaves this machine.\n"
)


def format_capture_facts(job: NormalizedJob) -> str:
    """Render the imported facts that are disclosed but not yet scored.

    Eight dimensions have no allocation rule, so these facts inform a human and change no
    number. Printing them unscored is the honest presentation: the alternative is importing
    fields nobody can see.
    """
    work = job.work
    lines = [
        "Imported listing facts — disclosed, not scored",
        f"  title                   {job.job_title}",
        f"  company                 {job.company.company_name}",
        f"  source platform         {job.provenance.source_platform}",
        f"  employment type         {work.employment_type.value}",
        f"  work arrangement        {work.work_arrangement.value}",
        f"  relocation status       {work.relocation_status.value}",
        f"  location text           {work.location_text}",
        f"  state restrictions      {work.state_restrictions}",
        f"  time zone restrictions  {work.time_zone_restrictions}",
        f"  base salary min USD     {job.compensation.base_salary_min_usd}",
        f"  base salary max USD     {job.compensation.base_salary_max_usd}",
        f"  company website         {job.company.company_website}",
        f"  official careers URL    {job.company.official_careers_url}",
        f"  years of experience     {job.years_of_experience_requirement}",
        "",
        "  Eight of nine dimensions have no approved allocation rule, so none of the above",
        "  affects any number below. Work authorization and clearance are deliberately absent",
        "  from this list: they inform hard blockers only, never a dimension score (D-5).",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    """Read a capture from stdin, print the dimension, and return an exit code."""
    if sys.stdin.isatty():
        sys.stdout.write(USAGE)
        return 0

    try:
        job = parse_capture(sys.stdin.read(), "stdin")
    except CaptureFormatError as error:
        sys.stdout.write(f"Capture could not be imported.\n\n  {error}\n")
        return 0

    dossier, explicit = load_dossier()
    config = load_assessment_config()
    result = score_technology_alignment(
        job.job_id, job.required_technologies, candidate_terms(dossier, explicit), config
    )
    sys.stdout.write(format_capture_facts(job))
    sys.stdout.write(
        format_result(result, "your approved dossier", "user-approved") + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
