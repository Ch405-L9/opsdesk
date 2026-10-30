# OpsDesk

**A local-first command center for solo and small service businesses.** Find local **leads**, research **government buyers**, track **jobs and applications** with an evidence-backed resume helper, and keep every **follow-up** in one place. It includes a terminal CLI, a private browser dashboard, and a business-formatted Excel workbook that keeps your edits.

- **You stay in control:** nothing runs on its own, and nothing is sent or submitted for you.
- **Free first:** it works with no keys (demo and manual entry). With keys it uses official free tiers, and shows the quota left before spending any.
- **Private:** your data stays in your own user folder. The dashboard only listens on `127.0.0.1`.

## Quick start
```bash
uv tool install .           # Python 3.12+
opsdesk init                # your business profile
opsdesk demo                # optional: sample data to try things
opsdesk today               # what's due
opsdesk dash                # dashboard at http://127.0.0.1:8765
opsdesk export              # OpsDesk.xlsx with dropdowns, checkboxes and follow-up colors
```

| Area | Commands |
|---|---|
| Leads | `leads find dentists in Austin TX` · `leads list` · `leads audit <item>` · `leads draft <item>` · `leads budget` |
| Bids | `bids fetch` · `bids rank` · `bids report` · `bids list` |
| Jobs & resume | `jobs template` · `jobs add job.md` · `jobs assess` · `jobs applied` · `resume init` · `resume draft <job>` |
| Workflow | `today` · `follow <item> +3d "note"` · `note` · `done` · `snooze` · `status` · `priority` · `contacted` · `show` |
| Workbook | `export` · `import-edits` |
| Admin | `doctor` · `keys set/list` · `backup` · `activity` · `where` |

**Docs:** [User manual](docs/USER_MANUAL.md) · [Architecture](docs/ARCHITECTURE.md) · [Quality review](docs/QUALITY_REVIEW.md) · [Build report](docs/BUILD_REPORT.md)

## Development
```bash
uv venv --python 3.12 && uv pip install -e ".[dev]"
uv run pytest          # 101 tests, coverage gate 80%
uv run ruff check src tests && uv run mypy
```

MIT licensed. Data sources: Google Places API and PageSpeed Insights API (Google terms apply), and USAspending.gov (public domain).
