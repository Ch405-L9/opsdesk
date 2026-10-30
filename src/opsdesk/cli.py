"""OpsDesk command line. Every command is run by you; nothing is scheduled, sent or submitted."""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from opsdesk import __version__, secrets, timeutil
from opsdesk.db import migrate
from opsdesk.paths import AppPaths, app_paths, ensure_directories
from opsdesk.profile import BusinessProfile, SalaryTargets, load_profile, save_profile
from opsdesk.workbench import get_item, label, list_items, resolve_key, workbench
from opsdesk.workflow import (
    PRIORITIES,
    STATUSES,
    WorkflowError,
    add_note,
    counts,
    follow,
    mark_done,
    set_fields,
    snooze,
    today_view,
)

app = typer.Typer(name="opsdesk", help="Local-first command center: leads, government bids, jobs and follow-ups.",
                  no_args_is_help=True, rich_markup_mode="rich", add_completion=True)
leads_app = typer.Typer(help="Find, audit and pitch local business leads.", no_args_is_help=True)
bids_app = typer.Typer(help="Research public-sector buyers and recompetes (USAspending).", no_args_is_help=True)
jobs_app = typer.Typer(help="Track jobs you capture; assess fit; record applications you made yourself.", no_args_is_help=True)
resume_app = typer.Typer(help="Your approved evidence and evidence-cited resume bullets.", no_args_is_help=True)
keys_app = typer.Typer(help="Manage optional API keys (stored privately, never in a repo).", no_args_is_help=True)
for sub, name in ((leads_app, "leads"), (bids_app, "bids"), (jobs_app, "jobs"), (resume_app, "resume"), (keys_app, "keys")):
    app.add_typer(sub, name=name)

console = Console()
err = Console(stderr=True)
JSON = Annotated[bool, typer.Option("--json", help="Machine-readable output.")]


def _paths() -> AppPaths:
    paths = ensure_directories(app_paths())
    migrate(paths.database_file)
    return paths


def _tz(paths: AppPaths) -> str:
    return load_profile(paths.profile_file).timezone


def _fail(message: str, code: int = 1) -> None:
    err.print(f"[bold red]✗[/] {message}")
    raise typer.Exit(code)


def _ok(message: str) -> None:
    console.print(f"[bold green]✓[/] {message}")


def _confirm_spend(what: str, yes: bool) -> None:
    if yes:
        return
    if not sys.stdin.isatty():
        _fail(f"{what} costs API quota. Re-run with --yes to confirm.", 2)
    answer = typer.prompt(f"{what}. Type 'spend' to continue", default="", show_default=False)
    if answer.strip().lower() != "spend":
        _fail("Cancelled. Nothing was spent.", 1)


def _emit(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2, default=str))


def _version(value: bool) -> None:
    if value:
        typer.echo(f"OpsDesk {__version__}")
        raise typer.Exit()


@app.callback()
def root(version: Annotated[bool, typer.Option("--version", callback=_version, is_eager=True, help="Show version.")] = False) -> None:
    """OpsDesk. Start with [bold]opsdesk init[/], then [bold]opsdesk today[/]."""


# --------------------------------------------------------------------------- setup
def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@app.command()
def init(
    business: Annotated[str | None, typer.Option(help="Business name")] = None,
    owner: Annotated[str | None, typer.Option(help="Your name (used to sign drafts)")] = None,
    services: Annotated[str | None, typer.Option(help="Comma-separated services")] = None,
    city: Annotated[str | None, typer.Option(help="Home city")] = None,
    state: Annotated[str | None, typer.Option(help="Two-letter state, e.g. GA")] = None,
    naics: Annotated[str | None, typer.Option(help="Comma-separated NAICS codes, e.g. 541511,541519")] = None,
    verticals: Annotated[str | None, typer.Option(help="Comma-separated target industries")] = None,
    certifications: Annotated[str | None, typer.Option(help="Self-declared: 8a,hubzone,wosb,edwosb,sdvosb,vosb")] = None,
    salary_min: Annotated[int | None, typer.Option(help="Minimum salary for job assessments")] = None,
    timezone: Annotated[str | None, typer.Option(help="IANA time zone")] = None,
    non_interactive: Annotated[bool, typer.Option("--non-interactive", help="Only apply the options given.")] = False,
) -> None:
    """Set up (or update) your business profile. Safe to re-run."""
    paths = _paths()
    current = load_profile(paths.profile_file)
    ask = (not non_interactive) and sys.stdin.isatty()

    def pick(value: Any, label_: str, default: Any) -> Any:
        if value is not None:
            return value
        if ask:
            shown = ", ".join(default) if isinstance(default, list) else (default or "")
            answer = typer.prompt(label_, default=str(shown), show_default=bool(shown))
            return _csv(answer) if isinstance(default, list) else answer
        return default

    data = current.model_dump()
    data["business_name"] = pick(business, "Business name", current.business_name)
    data["owner_name"] = pick(owner, "Your name", current.owner_name)
    data["services"] = _csv(services) if services is not None else pick(None, "Services (comma-separated)", current.services)
    data["home_city"] = pick(city, "Home city", current.home_city)
    data["home_state"] = (pick(state, "State (2 letters)", current.home_state) or "").upper()[:2]
    data["target_verticals"] = _csv(verticals) if verticals is not None else pick(None, "Target industries", current.target_verticals)
    data["naics_codes"] = _csv(naics) if naics is not None else pick(None, "NAICS codes (for bids)", current.naics_codes)
    data["set_aside_eligibility"] = _csv(certifications.lower()) if certifications is not None else current.set_aside_eligibility
    if salary_min is not None:
        data["salary_targets"] = SalaryTargets(minimum=salary_min, maximum=current.salary_targets.maximum).model_dump()
    if timezone:
        data["timezone"] = timezone
    try:
        profile = BusinessProfile.model_validate(data)
    except ValueError as exc:
        _fail(str(exc))
    save_profile(profile, paths.profile_file)
    _ok(f"Profile saved to {paths.profile_file}")
    console.print("Next: [bold]opsdesk doctor[/] · [bold]opsdesk leads find <what> in <where> --demo[/] · [bold]opsdesk dash[/]")


@app.command()
def doctor() -> None:
    """Check setup: folders, database, profile, keys and quotas."""
    from opsdesk.leads.service import quota_report

    paths = _paths()
    profile = load_profile(paths.profile_file)
    table = Table(title="OpsDesk doctor", show_lines=False)
    table.add_column("Check")
    table.add_column("Result")
    table.add_row("Version", __version__)
    table.add_row("Config folder", str(paths.config_dir))
    table.add_row("Data folder", str(paths.data_dir))
    table.add_row("Database", "ok" if paths.database_file.exists() else "missing")
    table.add_row("Profile", "ok" if profile.business_name else "[yellow]run `opsdesk init`[/]")
    table.add_row("Bids ready (NAICS)", ", ".join(profile.naics_codes) or "[yellow]add NAICS in init[/]")
    for name, present in secrets.configured(paths).items():
        table.add_row(f"Key: {name}", "set" if present else "[dim]not set (optional)[/]")
    for name, rep in quota_report(paths).items():
        table.add_row(f"Quota: {name}", f"{rep['remaining']} of {rep['usable']} {rep['unit']} left this month")
    console.print(table)


@keys_app.command("set")
def keys_set(name: Annotated[str, typer.Argument(help=", ".join(secrets.KEYS))]) -> None:
    """Store an API key privately (prompted, hidden)."""
    value = typer.prompt(f"Paste the {name} key", hide_input=True)
    try:
        secrets.save_secret(_paths(), name, value)
    except ValueError as exc:
        _fail(str(exc))
    _ok(f"{name} saved (mode 600).")


@keys_app.command("list")
def keys_list() -> None:
    """Show which optional keys are set (never the values)."""
    for name, present in secrets.configured(_paths()).items():
        console.print(f"{'✓' if present else '·'} {name}")


# --------------------------------------------------------------------------- leads
@leads_app.command("find")
def leads_find(
    query: Annotated[list[str], typer.Argument(help="e.g. dentists in Austin TX")],
    demo: Annotated[bool, typer.Option("--demo", help="Use synthetic sample data (free).")] = False,
    refresh: Annotated[bool, typer.Option("--refresh", help="Ignore the 14-day cache.")] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Confirm spending 1 Places call.")] = False,
    limit: Annotated[int, typer.Option(min=1, max=20)] = 20,
    as_json: JSON = False,
) -> None:
    """Find local businesses by category and place (cache-first; dry run before spending)."""
    from opsdesk.leads import service

    paths = _paths()
    text = " ".join(query)
    plan = service.plan_find(paths, text)
    if plan["cost_calls"] and not demo:
        console.print(f"Search [bold]{plan['industry']}[/] in [bold]{plan['location']}[/]: 1 Google Places call "
                      f"({plan['remaining']} of {plan['usable']} free calls left this month).")
        _confirm_spend("This search uses 1 Places call", yes)
    try:
        result = service.find(paths, text, confirmed=True, demo=demo, refresh=refresh, limit=limit)
    except (ValueError, RuntimeError, PermissionError) as exc:
        _fail(str(exc))
    if as_json:
        _emit({"source": result.source, "rows": result.rows})
        return
    table = Table(title=f"Leads: {plan['industry']} in {plan['location']}  ·  source: {result.source}")
    for col in ("Score", "Business", "Website", "Phone", "Rating", "Key"):
        table.add_column(col, overflow="fold")
    for r in result.rows:
        table.add_row(str(r.get("score", "")), r.get("name", ""), r.get("website") or "[red]none[/]",
                      r.get("phone") or "", f"{r.get('rating') or '-'} ({r.get('review_count') or 0})", r["key"])
    console.print(table)
    console.print(f"{result.inserted} new, {result.updated} updated. Next: [bold]opsdesk leads draft <key>[/] · "
                  "[bold]opsdesk follow <key> +3d[/]")


@leads_app.command("list")
def leads_list(status: Annotated[str | None, typer.Option(help="Filter by status")] = None,
               open_only: Annotated[bool, typer.Option("--open", help="Hide won/lost/skip")] = False,
               as_json: JSON = False) -> None:
    """List saved leads with your status and follow-ups."""
    _list("lead", status, open_only, as_json)


@leads_app.command("audit")
def leads_audit(ref: str, yes: Annotated[bool, typer.Option("--yes")] = False) -> None:
    """Run a Google Lighthouse (PageSpeed) audit on a lead's website (1 PSI call)."""
    from opsdesk.leads import service

    paths = _paths()
    with workbench(paths) as conn:
        key = _resolve(conn, ref)
    _confirm_spend("This audit uses 1 PageSpeed call", yes)
    try:
        payload = service.audit(paths, key, confirmed=True)
    except (KeyError, ValueError, PermissionError, RuntimeError) as exc:
        _fail(str(exc))
    audit = payload["audit"]
    console.print(Panel.fit("\n".join(f"{k}: {audit.get(k)}" for k in ("performance", "seo", "accessibility", "best_practices", "lcp_seconds")),
                            title=f"Audit · {payload.get('name')}"))
    for pain in payload.get("pains", [])[:3]:
        console.print(f"• [bold]{pain.get('headline')}[/] — {pain.get('angle')}")


@leads_app.command("draft")
def leads_draft(ref: str) -> None:
    """Write a cold email and call opener from measured evidence (a draft: you send it)."""
    from opsdesk.leads import service

    paths = _paths()
    with workbench(paths) as conn:
        key = _resolve(conn, ref)
    d = service.draft(paths, key)
    console.print(Panel(d["body"], title=f"Subject: {d['subject']}", subtitle="draft only · review before sending"))
    console.print(Panel(d["call_opener"], title="Call opener"))


@leads_app.command("budget")
def leads_budget() -> None:
    """Show free API quota left this month."""
    from opsdesk.leads.service import quota_report

    for name, rep in quota_report(_paths()).items():
        console.print(f"{name}: {rep['remaining']} of {rep['usable']} {rep['unit']} left "
                      f"(free tier {rep['limit']}; key {'set' if rep['key_present'] else 'not set'})")


# --------------------------------------------------------------------------- bids
@bids_app.command("fetch")
def bids_fetch(years: Annotated[int, typer.Option(min=1, max=10)] = 3,
               yes: Annotated[bool, typer.Option("--yes", help="Confirm the network request.")] = False) -> None:
    """Download public award data for your NAICS and state (free, no key)."""
    from opsdesk.bids import service

    paths = _paths()
    plan = service.plan_fetch(paths, years)
    if not plan["ready"]:
        _fail("Add NAICS codes first: opsdesk init --naics 541511,541519")
    console.print(f"USAspending: NAICS {', '.join(plan['naics'])}, state {plan['state'] or 'all'}, last {years} years; {plan['requests']}.")
    if not yes and sys.stdin.isatty() and not typer.confirm("Fetch now?", default=True):
        raise typer.Exit(1)
    if not yes and not sys.stdin.isatty():
        _fail("Network request not confirmed. Re-run with --yes.", 2)
    with console.status("Fetching public award data…"):
        counts_ = service.fetch(paths, years)
    _ok(f"Fetched {sum(counts_.values())} awards ({', '.join(f'{k} {v}' for k, v in counts_.items())}). Next: opsdesk bids rank")


@bids_app.command("rank")
def bids_rank(top: Annotated[int, typer.Option(min=1, max=200)] = 20, as_json: JSON = False) -> None:
    """Rank active awards by fit (prioritization, not odds of winning)."""
    from opsdesk.bids import service

    rows = service.ranked(_paths(), top)
    if as_json:
        _emit(rows)
        return
    if not rows:
        console.print("No bids yet. Run [bold]opsdesk bids fetch[/].")
        return
    table = Table(title="Bid watchlist · fit is priority, not a chance of winning")
    for col in ("Fit", "Ends", "Amount", "Buyer", "Incumbent", "Lane", "Key"):
        table.add_column(col, overflow="fold")
    for r in rows:
        table.add_row(str(r["fit"]), str(r["end"]), f"${r['amount']:,.0f}", r["sub_agency"], r["recipient"], r["lane"], r["wb_key"])
    console.print(table)


@bids_app.command("report")
def bids_report(out: Annotated[Path | None, typer.Option(help="Write Markdown here")] = None) -> None:
    """Write a Markdown buyer/recompete report from the local cache."""
    from opsdesk.bids import service

    paths = _paths()
    text = service.report(paths)
    target = out or (paths.data_dir / "exports" / f"bid_report_{timeutil.today(_tz(paths))}.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    _ok(f"Report written: {target}")


@bids_app.command("list")
def bids_list(status: Annotated[str | None, typer.Option()] = None,
              open_only: Annotated[bool, typer.Option("--open")] = False, as_json: JSON = False) -> None:
    """List bids with your status and follow-ups."""
    _list("bid", status, open_only, as_json)


# --------------------------------------------------------------------------- jobs + resume
@jobs_app.command("template")
def jobs_template() -> None:
    """Print a blank job capture to fill in."""
    from opsdesk.jobs.capture import TEMPLATE

    typer.echo(TEMPLATE)


@jobs_app.command("add")
def jobs_add(file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)]) -> None:
    """Save a job from a capture file, then assess it."""
    from opsdesk.jobs import service
    from opsdesk.jobs.capture import CaptureError

    paths = _paths()
    try:
        key, outcome = service.add(paths, file.read_text(encoding="utf-8"), origin=file.name)
        result = service.run_assessment(paths, key)
    except (CaptureError, ValueError) as exc:
        _fail(str(exc))
    _ok(f"Job {outcome}: {key}")
    _print_assessment(result)


@jobs_app.command("assess")
def jobs_assess(ref: str) -> None:
    """Re-assess a saved job against your current evidence and profile."""
    from opsdesk.jobs import service

    paths = _paths()
    with workbench(paths) as conn:
        key = _resolve(conn, ref)
    _print_assessment(service.run_assessment(paths, key))


@jobs_app.command("applied")
def jobs_applied(ref: str, note: Annotated[str, typer.Option(help="e.g. 'applied on company site'")] = "") -> None:
    """Record that YOU applied (saves a dated receipt of the posting). OpsDesk never submits."""
    from opsdesk.jobs import service

    paths = _paths()
    with workbench(paths) as conn:
        key = _resolve(conn, ref)
    path = service.record_applied(paths, key, note)
    _ok(f"Recorded. Receipt: {path}")


@jobs_app.command("list")
def jobs_list(status: Annotated[str | None, typer.Option()] = None,
              open_only: Annotated[bool, typer.Option("--open")] = False, as_json: JSON = False) -> None:
    """List jobs with your status and follow-ups."""
    _list("job", status, open_only, as_json)


@resume_app.command("init")
def resume_init() -> None:
    """Create your private evidence file with examples to replace."""
    from opsdesk.jobs import evidence

    path = evidence.init_file(_paths())
    _ok(f"Evidence file: {path}  (edit it; only approved, true facts)")


@resume_app.command("list")
def resume_list() -> None:
    """Show your evidence items."""
    from opsdesk.jobs import evidence

    try:
        items = evidence.load(_paths())
    except ValueError as exc:
        _fail(str(exc))
    if not items:
        console.print("No evidence yet. Run [bold]opsdesk resume init[/].")
    for i in items:
        console.print(f"[bold]{i.id}[/] {i.kind}: {i.title} — {', '.join(i.technologies)}")


@resume_app.command("draft")
def resume_draft(ref: str) -> None:
    """Resume bullets for a job, each one a verbatim evidence statement with its id."""
    from opsdesk.jobs import service

    paths = _paths()
    with workbench(paths) as conn:
        key = _resolve(conn, ref)
    bullets = service.draft_resume(paths, key)
    if not bullets:
        console.print("No evidence matches this job's required skills. Add evidence with `opsdesk resume init`.")
    for b in bullets:
        console.print(f"• {b['text']}  [dim]({b['evidence_id']} · {b['for']})[/]")


def _print_assessment(result: dict[str, Any]) -> None:
    tech = result["technology_alignment"]
    console.print(Panel.fit(
        f"Technology alignment: [bold]{tech if tech is not None else 'n/a'}[/]/100\n"
        f"Salary: {result['salary']}\nArrangement fits: {'yes' if result['arrangement_ok'] else 'no'}\n"
        f"Blockers: {', '.join(result['blockers']) or 'none found'}\n"
        f"Gaps (don't claim): {', '.join(result['gaps']) or 'none'}\n[dim]{result['disclaimer']}[/]",
        title="Assessment"))


# --------------------------------------------------------------------------- workflow
def _resolve(conn: sqlite3.Connection, ref: str) -> str:
    try:
        return resolve_key(conn, ref)
    except KeyError as exc:
        _fail(str(exc).strip("'\""))
        raise


def _list(area: str, status: str | None, open_only: bool, as_json: bool) -> None:
    with workbench(_paths()) as conn:
        items = list_items(conn, area, status=status, include_closed=not open_only)
    if as_json:
        _emit(items)
        return
    if not items:
        console.print(f"No {area}s yet.")
        return
    table = Table(title=f"{area.title()}s ({len(items)})")
    for col in ("Item", "Status", "Priority", "Follow-up", "Key"):
        table.add_column(col, overflow="fold")
    for i in items:
        due = i.get("followup_date") or ""
        table.add_row(label(i), i["status"], i["priority"], f"{due} {i.get('followup_note') or ''}".strip(), i["wb_key"])
    console.print(table)


@app.command()
def today(as_json: JSON = False) -> None:
    """What's overdue, due today and coming up (next 7 days)."""
    paths = _paths()
    with workbench(paths) as conn:
        view = today_view(conn, _tz(paths))
        tallies = counts(conn)
    if as_json:
        _emit(view)
        return
    styles = {"overdue": "bold red", "today": "bold yellow", "upcoming": "cyan"}
    empty = True
    for bucket, rows in view.items():
        if not rows:
            continue
        empty = False
        table = Table(title=f"{bucket.title()} ({len(rows)})", title_style=styles[bucket], show_header=True)
        for col in ("Due", "Item", "Note", "Status", "Key"):
            table.add_column(col, overflow="fold")
        for i in rows:
            table.add_row(i["followup_date"], label(i), i.get("followup_note") or "", i["status"], i["wb_key"])
        console.print(table)
    if empty:
        console.print("Nothing due in the next 7 days. Add one with [bold]opsdesk follow <item> +3d \"note\"[/].")
    summary = " · ".join(f"{a}s {sum(t.values())}" for a, t in tallies.items())
    console.print(f"[dim]{summary}[/]")


@app.command("follow")
def follow_cmd(ref: str, when: str, note: Annotated[str, typer.Argument()] = "") -> None:
    """Set a follow-up: when = YYYY-MM-DD, today, tomorrow, +3d, +2w or a weekday."""
    paths = _paths()
    try:
        date = timeutil.parse_when(when, _tz(paths))
        with workbench(paths) as conn:
            key = _resolve(conn, ref)
            follow(conn, key, date, note)
    except (ValueError, WorkflowError) as exc:
        _fail(str(exc))
    _ok(f"Follow-up {date.isoformat()} set for {key}")


@app.command("note")
def note_cmd(ref: str, text: str) -> None:
    """Append a dated note to an item."""
    paths = _paths()
    with workbench(paths) as conn:
        key = _resolve(conn, ref)
        add_note(conn, key, text, tz=_tz(paths))
    _ok(f"Note added to {key}")


@app.command("done")
def done_cmd(ref: str) -> None:
    """Mark an item's follow-up done."""
    with workbench(_paths()) as conn:
        key = _resolve(conn, ref)
        mark_done(conn, key)
    _ok(f"Done: {key}")


@app.command("snooze")
def snooze_cmd(ref: str, days: Annotated[int, typer.Argument(min=1, max=365)] = 3) -> None:
    """Push a follow-up out by N days (default 3)."""
    paths = _paths()
    with workbench(paths) as conn:
        key = _resolve(conn, ref)
        when = snooze(conn, key, days, _tz(paths))
    _ok(f"Snoozed {key} to {when.isoformat()}")


@app.command("status")
def status_cmd(ref: str, value: str) -> None:
    """Set an item's status (see `opsdesk statuses`)."""
    with workbench(_paths()) as conn:
        key = _resolve(conn, ref)
        try:
            set_fields(conn, key, status=value)
        except WorkflowError as exc:
            _fail(str(exc))
    _ok(f"{key} → {value}")


@app.command("priority")
def priority_cmd(ref: str, value: Annotated[str, typer.Argument(help=" | ".join(PRIORITIES))]) -> None:
    """Set an item's priority: high, normal or low."""
    with workbench(_paths()) as conn:
        key = _resolve(conn, ref)
        try:
            set_fields(conn, key, priority=value)
        except WorkflowError as exc:
            _fail(str(exc))
    _ok(f"{key} priority → {value}")


@app.command("contacted")
def contacted_cmd(ref: str) -> None:
    """Tick 'Contacted' for an item."""
    with workbench(_paths()) as conn:
        key = _resolve(conn, ref)
        set_fields(conn, key, contacted=1)
    _ok(f"Contacted: {key}")


@app.command("show")
def show_cmd(ref: str, as_json: JSON = False) -> None:
    """Show everything about one item."""
    with workbench(_paths()) as conn:
        key = _resolve(conn, ref)
        item = get_item(conn, key)
    if as_json:
        _emit(item)
        return
    assert item is not None
    body = "\n".join(f"[bold]{k}[/]: {v}" for k, v in item.items() if k not in {"capture_text", "audit", "pains"} and v not in (None, "", []))
    console.print(Panel(body, title=label(item)))


@app.command("statuses")
def statuses_cmd() -> None:
    """List valid statuses per area."""
    for area, values in STATUSES.items():
        console.print(f"[bold]{area}[/]: {', '.join(values)}")


# --------------------------------------------------------------------------- export / dashboard / maintenance
def _default_export(paths: AppPaths) -> Path:
    return paths.data_dir / "exports" / "OpsDesk.xlsx"


@app.command("export")
def export_cmd(out: Annotated[Path | None, typer.Option(help="Workbook path")] = None,
               area: Annotated[list[str] | None, typer.Option(help="lead, bid, job (repeatable)")] = None) -> None:
    """Write the business-formatted workbook (imports your edits from the last copy first)."""
    from opsdesk.export.xlsx import ExportLocked, export

    paths = _paths()
    target = out or _default_export(paths)
    areas = area or ["lead", "bid", "job"]
    bad = [a for a in areas if a not in {"lead", "bid", "job"}]
    if bad:
        _fail(f"Unknown area(s): {', '.join(bad)}")
    try:
        with workbench(paths) as conn:
            result = export(conn, target, areas, _tz(paths))
    except ExportLocked as exc:
        _fail(str(exc))
    _ok(f"Workbook: {result['path']}  ({', '.join(f'{k}s {v}' for k, v in result['counts'].items())}; "
        f"{result['imported_edits']} edited rows imported first)")


@app.command("import-edits")
def import_cmd(file: Annotated[Path | None, typer.Argument()] = None) -> None:
    """Read your changes from the workbook into OpsDesk without re-exporting."""
    from opsdesk.export.xlsx import ExportLocked, import_edits

    paths = _paths()
    try:
        with workbench(paths) as conn:
            rep = import_edits(conn, file or _default_export(paths), _tz(paths))
    except ExportLocked as exc:
        _fail(str(exc))
    _ok(f"Imported {rep['applied']} edited rows (checked {rep['rows']}).")
    for e in rep["errors"]:
        err.print(f"[yellow]![/] {e}")


@app.command()
def dash(port: Annotated[int, typer.Option(min=1024, max=65535)] = 8765,
         open_browser: Annotated[bool, typer.Option("--open/--no-open")] = True) -> None:
    """Open the local dashboard (only this computer can reach it)."""
    import threading
    import webbrowser

    import uvicorn

    from opsdesk.web.app import create_app

    url = f"http://127.0.0.1:{port}"
    console.print(f"Dashboard: [bold]{url}[/]  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(_paths()), host="127.0.0.1", port=port, log_level="warning")


@app.command()
def demo() -> None:
    """Load sample leads and a sample job so you can try everything (free, no keys)."""
    from opsdesk.jobs import evidence
    from opsdesk.jobs import service as jobs

    paths = _paths()
    from opsdesk.leads import service as leads

    leads.find(paths, "dentists in Springfield IL", demo=True)
    leads.find(paths, "roofers in Springfield IL", demo=True)
    evidence.init_file(paths)
    sample = ("title: Web Developer (Demo)\ncompany: Example Co\nurl: https://jobs.example.com/web-dev\n"
              "location: Remote, US\narrangement: remote\nemployment: contract\nsalary_min: 60000\nsalary_max: 85000\n"
              "required:\n- Python\n- JavaScript\n- React\npreferred:\n- Lighthouse\n---\nSynthetic demo posting.\n")
    key, _ = jobs.add(paths, sample, origin="demo")
    jobs.run_assessment(paths, key)
    with workbench(paths) as conn:
        first = list_items(conn, "lead")[0]["wb_key"]
        follow(conn, first, timeutil.today(_tz(paths)), "Demo: call about their website")
    _ok("Demo data loaded. Try: opsdesk today · opsdesk export · opsdesk dash")


@app.command()
def backup(out: Annotated[Path | None, typer.Option()] = None) -> None:
    """Copy your database safely (SQLite backup API)."""
    paths = _paths()
    target = out or (paths.data_dir / "backups" / f"workbench_{timeutil.now(_tz(paths)).strftime('%Y%m%d_%H%M%S')}.sqlite3")
    target.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(paths.database_file)
    dst = sqlite3.connect(target)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    _ok(f"Backup: {target}")


@app.command()
def activity(limit: Annotated[int, typer.Option(min=1, max=500)] = 25) -> None:
    """Show the audit log of recent actions."""
    with workbench(_paths()) as conn:
        rows = conn.execute("SELECT created_at, actor, action, wb_key FROM activity ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    table = Table(title="Activity")
    for col in ("When", "Who", "Action", "Item"):
        table.add_column(col)
    for r in rows:
        table.add_row(r["created_at"], r["actor"], r["action"], r["wb_key"] or "")
    console.print(table)


@app.command()
def where() -> None:
    """Show where your files live."""
    paths = _paths()
    console.print(f"Config: {paths.config_dir}\nData:   {paths.data_dir}\nExports: {paths.data_dir / 'exports'}")
    if shutil.which("xdg-open"):
        console.print("[dim]Open with: xdg-open <folder>[/]")


def main() -> None:
    app()
