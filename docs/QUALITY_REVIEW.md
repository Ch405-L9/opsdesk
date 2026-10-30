# Quality review: OpsDesk v1.0.0 against comparable tools and professional practice
Reviewed 2026-10-30. Comparisons are at the feature-category level, from public product descriptions; no competitor was benchmarked hands-on.

## Comparable products
| Need | Typical tools | What they do well | What OpsDesk does instead |
|---|---|---|---|
| Lead pipeline / CRM | HubSpot free CRM, Pipedrive, Streak | Stages, tasks and due dates, activity timeline | Same stage → task → timeline model (status, follow-ups, activity log), local and free. No email sync or sending, by design. |
| Local lead discovery | Apollo-style prospect databases, Maps scrapers | Volume | Official Google Places API, quota-capped, cache-first. Scores need: businesses with **no website** surface, which search engines can't show. |
| Gov-contracting research | HigherGov, GovSpend, GovTribe | Large award and solicitation databases | Free USAspending data ranked by buyer frequency, recompete window and set-aside lane. Prioritization only; no "win probability". |
| Job tracking | Teal, Huntr | Kanban plus resume tailoring | Status board, an **evidence-cited** resume (no invented claims), a dated application receipt, and no auto-apply. |
| Spreadsheet workflows | Google Sheets / Excel templates | Familiar, flexible | A generated workbook with validation, conditional formatting and a three-way-merge import that never loses edits. |
| CLI ergonomics | gh, taskwarrior, hledger | Fast keyboard workflows, scriptable | Typer CLI with fuzzy item names, date shorthands, `--json` and shell completion. |

## Professional checklist
### CLI (clig.dev guidelines)
| Practice | Status |
|---|---|
| `--help` on every command, examples in the help text | ✅ |
| `--version` | ✅ |
| Errors on stderr with a fix suggestion; non-zero exit codes (1 user error, 2 needs confirmation) | ✅ |
| Machine-readable `--json` on `list`, `today`, `show` and `find` | ✅ |
| Confirmation before anything that costs quota; non-interactive runs refuse without `--yes` | ✅ |
| Respects `NO_COLOR` and non-TTY output (Rich) | ✅ |
| Shell completion (`opsdesk --install-completion`) | ✅ |
| No hidden background work: no daemons, no schedulers | ✅ (enforced by a test) |

### Dashboard (WCAG 2.2 AA, OWASP for local web apps)
| Practice | Status |
|---|---|
| Loopback-only bind, Host-header allowlist (DNS-rebinding defense) | ✅ |
| CSRF token on every POST | ✅ |
| CSP `default-src 'self'`, no CDN, X-Frame-Options DENY, nosniff, no-referrer | ✅ |
| Skip link, visible focus ring, labeled inputs, `aria-current` navigation | ✅ |
| Dark-mode support (`prefers-color-scheme`); status colors paired with text | ✅ |
| Server-rendered and works without JavaScript (JS only adds sorting and the "/" shortcut) | ✅ |
| Empty states and guidance on every page | ✅ |

### Data and spreadsheet
| Practice | Status |
|---|---|
| Tool data and user workflow kept in separate tables; importers never write user fields | ✅ (tested) |
| Idempotent upserts by stable keys, content-hash change detection, nothing deleted | ✅ (tested) |
| Three-way merge on re-import; stale workbook can't undo newer edits; notes append-only | ✅ (tested) |
| Formula-injection guard on all text cells | ✅ (tested) |
| Dropdowns from a hidden list sheet, ☐/☑ checkboxes, date validation, frozen panes, filters, overdue/today/soon/closed formatting | ✅ (tested) |
| Refuses to overwrite an open workbook; `.prev.xlsx` backup | ✅ (tested) |
| SQLite WAL, migrations, safe backup command | ✅ |
| Time-zone-aware follow-ups, DST-day test | ✅ |

### Privacy and safety
| Practice | Status |
|---|---|
| All personal data in OS user folders; `profile.yaml`, `secrets.yaml` and evidence files are mode 600 | ✅ |
| No contact details allowed in resume evidence | ✅ (tested) |
| No browser automation, email sending, shell or scheduler in the source | ✅ (tested) |
| No personal data in tracked files | ✅ (tested) |
| Official APIs only; no LinkedIn or Indeed scraping | ✅ |

## Results
- 101 automated tests: unit, integration, CLI end-to-end, dashboard (TestClient) and compliance.
- Branch coverage 86%.
- ruff clean, mypy clean.
- Manual smoke test: init → demo → today → follow / note / status → draft → export → doctor, plus dashboard screenshots.

## Known gaps (v1.1 candidates)
1. **SAM.gov open solicitations:** v1 ranks past awards (who buys) but doesn't list live solicitations yet.
2. **Optional local model** (Ollama tool registry, ARCHITECTURE §5): not built. Every action is already scriptable through `--json` and the CLI.
3. **Job sources:** jobs are captured by paste. Official Greenhouse/Lever/USAJOBS adapters are next.
4. **XLSX native checkboxes:** ☐/☑ dropdowns are used, so the file works in Excel, LibreOffice and Google Sheets alike.
5. **Multi-user:** single-user by design.
