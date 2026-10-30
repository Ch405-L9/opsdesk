# OpsDesk: architecture and recommendations

This is a generalized version of an architecture review of three working prototypes, copied into `reference/`. OpsDesk is for any solo or small service business, not one person.

## 1. What exists (in `reference/`)
| Prototype | What it does | Strengths to keep | Known problems |
|---|---|---|---|
| `leadfinder/` | Finds local businesses by category and city (Google Places Text Search), audits their sites (PageSpeed / Lighthouse), scores fit, writes pain points, a cold email and a call opener. Plain-English CLI (`icp find me dentists in Austin TX`). Outcome tracking (`icp called/won/lost X`) | Budget ledger plus 14-day search cache, lead scoring, pain-point evidence, tests | Writes CSV/XLSX into the repo; secrets file in the project root; scrapers (`root_scraper.py`, `free_scraper.py`, `ddg.py`) are fragile and partly blocked |
| `bidfinder/` | Pulls public federal award data (USAspending, no key) for chosen NAICS codes and a state; ranks repeat buyers, recompete windows, small-business set-asides and incumbents to team with; Markdown report | Pure, offline ranking with provenance per fetch; `csv_safe.py` (formula-injection guard), `redact.py`, `db.py` migration runner | Hard-coded NAICS/state; Markdown only |
| `vetted/` | Job and contract copilot: validates the user's approved evidence, assesses job "captures" against a private dossier (technology alignment, salary, arrangement), review-only drafts. **Never submits anything** | Strict no-submit safety gate, pydantic models, 520 tests, compliance tests (no personal data, no browser automation) | `config/policy/*.yaml` holds one person's salary bands and scoring decisions; replace with neutral, documented defaults. No database yet |

They are separate apps today: separate runtimes and data stores, with no shared IDs or CLI.

## 2. Target shape
- **One CLI front door**: `opsdesk <area> <verb>` (Typer). Areas: `leads`, `bids`, `jobs`, `resume`, plus cross-cutting `today`, `follow`, `note`, `done`, `sync`, `export`, `import-edits`, `dash`, `tools`, `backup`, `doctor`, `init`.
- **One workbench database**: SQLite in the user data dir (`platformdirs`), never inside the repo. Each module owns its domain tables. **The user's workflow data (status, priority, done, contacted, follow-up date and note, notes) lives in separate tables that importers and fetchers never write.** Re-fetching can never erase the user's work.
- **Modules, not separate apps**: port the three prototypes into `opsdesk/leads`, `opsdesk/bids`, `opsdesk/jobs` (jobs includes the resume/evidence side). Keep their logic and tests; drop the fragile scrapers unless they pass tests.
- **A user profile** (`opsdesk init` wizard → `profile.yaml` in the config dir): business name, services, home city/state and radius, target verticals, NAICS codes, set-aside eligibility (self-declared, never inferred), salary targets, API keys (or env vars). Nothing user-specific is hard-coded.

### Core tables (suggested)
`source` (provenance: tool, kind, ref, fetched_at, terms_note) · `lead` · `bid` · `job` · `application` · `contact` (PII) · **`workflow`** (wb_key PK, status, priority, done, contacted, followup_date, followup_note, updated_at, updated_by) · `followup` · `note` (append-only) · `activity` (audit log, including model actions) · `sync_run` · `export` / `export_cell` (snapshot values for the round-trip merge).
Stable keys: `lead:<website host or name+phone hash>`, `bid:usaspending:<generated_internal_id>`, `job:<host>:<req id or url hash>`. Upsert with `ON CONFLICT DO UPDATE`, skip unchanged rows by content hash, never delete.

## 3. Spreadsheet export (the user's daily tool)
- openpyxl. One workbook per area, plus a combined "Command Center" workbook: Today, Leads, Bids, Jobs, plus hidden `_lists` and `_meta` sheets.
- **User-owned columns on the left, with a yellow header**: Status, Priority, Done, Contacted, Follow-up Date, Follow-up Note, Notes. Tool columns follow, with a navy header and white bold text. Hidden column A holds `wb_key`.
- Freeze panes, auto-filter, fixed column widths, real dates (`yyyy-mm-dd`), money and percent formats, row banding through conditional formatting.
- **Dropdowns**: list validation pointing at `_lists`. (In openpyxl `showDropDown=True` *hides* the arrow; don't set it.)
- **Checkboxes**: ☐/☑ list validation, centered, with green fill when ☑. Works the same in Excel, LibreOffice and Google Sheets. The importer also accepts TRUE/x/yes/1.
- **Conditional formatting**: overdue and not done = red; due today = amber; due in 3 days = pale yellow; closed statuses = grey.
- Hyperlinks for websites, postings and award pages.
- **Formula-injection guard on every text cell** (scraped names can start with `=`, `+`, `-`, `@`). Reuse `csv_safe.py`.
- **Round trip (three-way merge)**: `export` first imports the previous file. A cell is applied only if the user changed it since the last export (compare with `export_cell`). Notes append, never replace. Refuse to run if the file is open (lock file present). Keep a `.prev.xlsx`.

## 4. Dashboard
FastAPI + Jinja2 + HTMX (vendored, no CDN), bound to **127.0.0.1 only**, Host-header check, CSRF on POST. Pages: **Today** (overdue / due / next 7 days, one-click Done, Snooze, Note), **Leads** (kanban + table + API budget widget), **Bids** (buyers, recompete windows, eligibility notes), **Jobs & Applications** (ledger, assessment, "applied manually" stamp), **Resume / Evidence** (evidence items, which drafts cite them, gaps), **Activity** (audit log), **Settings** (profile, keys, quotas). Edits go through the same service layer as the CLI, so the CLI, the dashboard and spreadsheets always agree.

## 5. Local model integration (optional, Ollama)
- Plain JSON function-calling via Ollama `/api/chat` with `tools`. No MCP is needed for small models; a read-only MCP server can come later from the same registry.
- A tool registry with risk classes: `read` (runs), `draft` (workbench writes only, logged, undoable), `spend` (dry run shows cost, then the user must type `spend` at the terminal; never a model-settable parameter), `external` (send, submit, post) **not exposed at all**.
- At most 8 tools, strict JSON schemas (enums, `additionalProperties:false`), argument validation, outputs trimmed. Scraped text is wrapped as untrusted. **Never give the model a shell.**

## 6. Hard rules
- Nothing runs on a schedule. Every action is a command the user types or clicks.
- Never submit applications, send email or post anywhere automatically. Drafts only.
- API spend: show remaining free quota; `spend` commands dry-run first; respect provider free tiers (e.g., Google Places Text Search Enterprise has 1,000 free calls/month; recommend users also set a Google Cloud quota cap).
- Personal data lives only in the user data dir; repo, fixtures and examples are synthetic. Public/shareable exports are redacted (`redact.py`).
- Scores are prioritization, never odds of winning or getting hired. Unknown eligibility is shown as UNKNOWN and blocks "pursue".
- Respect data-source terms: official APIs (Places, PageSpeed, USAspending, SAM.gov, USAJOBS, Greenhouse/Lever public boards) over scraping; no LinkedIn/Indeed scraping or logins.
- Dates and deadlines in the user's configured time zone (default America/New_York), DST-safe.
