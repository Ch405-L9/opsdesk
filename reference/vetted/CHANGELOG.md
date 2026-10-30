# Changelog

## 0.1.0.dev2 (2026-10-30), phase 2 assessment core
- Ported careerops-local's pure assessment core into `vetted.core`: domain models, enums, policy config and schema, capture parser, blockers, risk flags, evidence matching, technology-alignment scoring, and the listing report.
- The candidate dossier is no longer hard-coded: it loads from your private `data/candidate/dossier.yaml`, validated by the frozen model (unknown fields such as contact details are rejected). Synthetic example in `config/examples/`.
- New command: `vetted assess CAPTURE.md [...] [--dossier PATH]`.
- Ported 478 careerops tests (compliance + unit) against a synthetic dossier. Dropped the parity tests and the "calibration against the real dossier" tests, which depended on personal data. Added dossier and CLI tests. 520 tests total, coverage 85% (gate raised to 80%).
- Lint config added (ruff, 100 columns); mypy strict clean.

## 0.1.0.dev1 (2026-10-30), phase 1 skeleton
- New repository built from a file copy of Web Agent Resume Builder (no history carried over).
- Package renamed to `vetted`; single CLI entry point `vetted`.
- Removed: live browser inspection, Playwright/Chromium dependency, the single-site target allowlist, résumé-upload setting, unused chromadb/ollama/httpx dependencies, empty CI files, site-specific docs and scripts.
- Added: working CI (ruff, mypy, pytest, gitleaks), Makefile, compliance tests for the no-submit surface and for personal data in tracked files.
