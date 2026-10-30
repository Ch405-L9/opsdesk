# Vetted (working name)

A local-first job copilot that refuses to spam. It checks whether a posting is real, ties every résumé line to evidence you approved, and leaves **Submit** to you.

> **Status: v0.1.0.dev2, phase 2 (assessment core).** `vetted assess` ranks job captures against your approved dossier on technology alignment, with every match citing its evidence. It also validates local candidate evidence and builds a review-only draft summary. Official job sources, evidence-cited drafts and contract mode come later. See `docs/ROADMAP.md`.

## Safety boundary (enforced by tests)
- No submit, no upload, no login, no stored platform credentials, no browser automation.
- `ALLOW_SUBMIT` must be explicitly `false`. Any other value fails configuration loading.
- Every command prints: **NO APPLICATION HAS BEEN SUBMITTED. HUMAN REVIEW AND MANUAL SUBMISSION ARE REQUIRED.**
- Compliance tests fail the build if browser/automation imports, `.click()` calls, credential fields, personal emails, phone numbers, home paths or tax IDs appear in tracked files.

## Install (Python 3.12)
```bash
uv sync --extra dev
cp .env.example .env   # sets ALLOW_SUBMIT=false (required)
uv run vetted assess config/examples/capture.example.md --dossier config/examples/dossier.example.yaml
uv run vetted --help
uv run vetted doctor
```

## Commands
| Command | What it does |
|---|---|
| `vetted version` | Version and safe runtime configuration |
| `vetted init` / `vetted doctor` | Create and check local, gitignored runtime folders |
| `vetted candidate validate` | Validate your local profile and approved evidence records |
| `vetted retrieval prepare` | Build a deterministic local retrieval manifest (no embeddings) |
| `vetted draft` / `vetted review-draft` | In-memory, review-only draft summary |
| `vetted assess CAPTURE.md [MORE.md] [--dossier PATH]` | Rank job captures against your dossier (technology alignment, salary, arrangement). Decision support only; one of nine dimensions, not a match score |

## Your dossier (private)
Copy `config/examples/dossier.example.yaml` to `data/candidate/dossier.yaml` (gitignored) and replace every value with your own approved facts. Unknown fields, including contact details, are rejected. Capture each job with `docs/JOB_CAPTURE_TEMPLATE.md` (example: `config/examples/capture.example.md`).

Scoring policy lives in `config/policy/*.yaml`. The shipped values are the original author's decisions (including salary bands), recorded in `docs/SCORING_DECISIONS.md`; edit them to match your own targets.

Your data lives in gitignored `data/` and `artifacts/` folders. Nothing personal belongs in the package.

## Origins and credits
Vetted merges the best parts of six earlier BADGRTechnologies job tools. The base is Web Agent Resume Builder (MIT); the assessment core comes from careerops-local. Third-party code is credited where it is used.

## License
MIT. See `LICENSE`.
