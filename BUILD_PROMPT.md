# Build prompt: OpsDesk

You are building **OpsDesk** from start to finish: a polished, production-ready, local-first command center for solo and small service businesses (web, IT, AI and field-service freelancers). It finds **leads**, finds **government bids**, tracks **jobs and applications** with an evidence-backed **resume helper**, and keeps every follow-up in one place. You have full freedom in how you build it. The ideas and rules below are recommendations, plus a few hard lines. If you see something wrong in the reference code or in this prompt, fix it and note why.

## Repo
Everything you need is in this repository:
- `docs/ARCHITECTURE.md`: the target design. **Read it first.**
- `reference/leadfinder/`, `reference/bidfinder/`, `reference/vetted/`: three working prototypes with tests. Reuse their logic and tests, port them into one app, and improve them. Don't ship them as separate apps.

Build the product at the repo root (`pyproject.toml`, `src/opsdesk/`, `tests/`). Leave `reference/` read-only, and delete it in your final commit once everything is ported.

## What "done" looks like
A new user can run:
```
uv tool install .            # or: pipx install .
opsdesk init                 # wizard: business profile, services, city/radius, NAICS, keys (optional)
opsdesk leads find dentists in Austin TX
opsdesk bids fetch && opsdesk bids rank
opsdesk jobs assess posting.md
opsdesk today
opsdesk export all           # beautiful XLSX with dropdowns, checkboxes, follow-ups
opsdesk dash                 # http://127.0.0.1:8765
```
…and it works on Linux, macOS and Windows, with no paid services required. With no API keys it still works through demo mode and synthetic data, plus manual entry. With keys, it uses free tiers and shows remaining quota.

## Recommended stack
Python 3.12, uv, Typer + Rich (CLI), pydantic, SQLite (stdlib `sqlite3` with a small migration runner; see `reference/bidfinder/badgr_funding/db.py`), openpyxl (XLSX), FastAPI + Jinja2 + HTMX vendored locally (dashboard), httpx, platformdirs, pytest. Keep dependencies few. Ollama support is optional.

## Build in shippable phases (commit after each, with tests passing)
1. **Skeleton**: package, `opsdesk init/doctor/version`, profile in the user config dir, workbench DB in the user data dir, CI (ruff, mypy, pytest, gitleaks).
2. **Leads**: port leadfinder discovery (Places Text Search, field-masked), cache, budget ledger, audit (PageSpeed API), scoring, pain points, outreach drafts, outcomes.
3. **Bids**: port bidfinder (USAspending fetch with provenance, offline ranking), with NAICS, state and set-asides from the profile. Add SAM.gov opportunities if a free key is set.
4. **Jobs + resume**: port vetted (no-submit gate, dossier from a private user file, `assess`, evidence-cited drafts), and add an application ledger with a dated posting snapshot ("application receipt").
5. **Workflow layer**: `today / follow / note / done`, statuses and priorities, an append-only activity log.
6. **XLSX export + round-trip import**: follow ARCHITECTURE §3 exactly. This is the feature users touch every day.
7. **Dashboard**: the pages in ARCHITECTURE §4. Make it beautiful: clean typography, generous spacing, accessible contrast (WCAG 2.2 AA), keyboard-friendly, fast, an empty state on every page, and a "demo data" toggle.
8. **Optional local model**: the tool registry in ARCHITECTURE §5.
9. **Polish + release**: README with screenshots and a GIF, a quick start under 5 minutes, `CHANGELOG`, `LICENSE` (MIT), and a v1.0.0 tag.

## Do
- Make the user's edits sacred: fetchers and importers never write workflow fields. Use three-way merge on spreadsheet re-import.
- Dry-run and confirm anything that spends API quota. Show "X of Y free calls left this month".
- Use official APIs and public JSON (Places, PageSpeed, USAspending, SAM.gov, USAJOBS, Greenhouse/Lever public boards). Cache aggressively.
- Guard every exported text cell against formula injection.
- Store dates timezone-aware, in the user's configured zone (default America/New_York). Test across DST.
- Write tests for: parsers, dedupe/keys, statuses, deadlines/follow-up buckets, export formatting (reload and assert validations and conditional formats), round-trip merge, redaction, the no-submit gate, quota guard.
- Ship synthetic fixtures and demo data only.

## Don't
- Don't schedule anything (no cron, timers or background jobs). Users run commands.
- Don't send email, post, submit applications or log into job boards. Produce drafts only.
- Don't scrape LinkedIn, Indeed or ZipRecruiter, or anything whose terms forbid it. Don't spoof user agents, and don't ignore robots.txt (fail closed).
- Don't give a model a shell or any send/submit tool.
- Don't hard-code any person's name, location, NAICS, salary or keys. The reference `vetted/config/policy/*.yaml` salary bands belong to one person: replace them with neutral, documented defaults from the profile.
- Don't present scores as odds of winning or getting hired. Show unknown eligibility as UNKNOWN.
- Don't commit secrets or real business or personal data. Put `*.xlsx`, `*.csv`, `.env` and data dirs in `.gitignore`.

## Hand-off notes
When you finish, write `docs/BUILD_REPORT.md`: what you built, what you changed from this prompt and why, known gaps, and test and coverage numbers. A second team will review UX/UI and harden it afterward, so favor clear structure over cleverness.
