# Build report: OpsDesk v1.0.0

## How it was built
1. **Manus** started from `BUILD_PROMPT.md`. It completed phase 1 (skeleton: user paths, profile model, SQLite migrations, CLI stub) and phases 2–3 (leads, bids), then ran out of credits partway through the jobs port.
2. Manus's download was flattened: every folder collapsed into one level, so files with the same name overwrote each other. Only its skeleton (`paths.py`, `profile.py`, `db.py`, migrations, demo-lead model) and part of its leads service survived intact. Its bids, SAM.gov and jobs modules were lost.
3. Claude finished the build:
   - kept Manus's skeleton;
   - rebuilt leads, bids and jobs on one shared workbench;
   - added the workflow layer, the XLSX round trip and the dashboard;
   - wrote tests, CI and docs.

## Changes from the prompt, and why
- **Jobs engine:** a lean evidence-tier matcher replaced porting the full careerops policy engine. The policy engine depended on one person's scoring decisions and salary bands, which the prompt said to remove. Same principles: evidence-cited, gaps shown, no verdict.
- **Dashboard without HTMX:** plain forms with POST-redirect-GET, plus a little vanilla JS. Nothing is vendored or fetched from a CDN, and every page works with JavaScript off.
- **Optional local model (phase 8): not built.** The CLI's `--json` output covers scripting. Listed as v1.1.
- **SAM.gov solicitations: deferred** (needs a key and term review). Bids v1 uses USAspending only.
- Removed unused key slots (SAM.gov, Hunter) so setup doesn't show settings that don't do anything.
- `reference/` was deleted from this branch after porting, as the prompt asked. It's still in `master` history.

## Bugs found and fixed during the build
- Two demo businesses shared one URL, so one silently overwrote the other.
- The call opener ignored the user's name.
- The cold email claimed "I ran a Lighthouse audit" when no audit had been run. It now offers a free check instead.
- The lead score collided with the workflow "priority" field.
- The phone-number key regex was mis-escaped.
- Real-looking domains in ported test fixtures were replaced with reserved `.example` domains.

## Verification
- `uv run pytest`: **101 passed**, branch coverage **86%** (gate 80%).
- `ruff check` and `mypy`: clean.
- Manual smoke test through every main command, plus headless-browser screenshots of the dashboard.

## Known gaps
See [QUALITY_REVIEW.md](QUALITY_REVIEW.md) → Known gaps.
