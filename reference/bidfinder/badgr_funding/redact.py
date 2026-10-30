"""Pattern scan for secrets and sensitive identifiers in project text files.

Limitations (documented in docs/PRIVACY.md): regex heuristics only. Misses
secrets in unusual formats, images, PDFs and encoded blobs, and can raise false
positives on long numbers. A clean scan is not proof that no sensitive data exists.

Files matching SKIP_NAME_PATTERNS are never opened, so the credential-bearing
original (.env*, secret*) is not read by this tool.
"""
import fnmatch
import re
import sys
from pathlib import Path

SKIP_NAME_PATTERNS = (".env*", "*secret*", "*.sqlite*", "*.db")
SKIP_DIRS = {".git", "__pycache__", "data", ".venv", "backups", "badgr_legal", "private"}
TEXT_SUFFIXES = {".md", ".csv", ".json", ".txt", ".py", ".sql", ".toml", ".yml", ".yaml", ".html", ""}

PATTERNS = {
    "ein_like": re.compile(r"\b\d{2}-\d{7}\b"),
    "ssn_like": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "routing_or_account_like": re.compile(r"(?<![\d.])\d{9,17}(?![\d.])"),
    "card_like": re.compile(r"\b(?:\d{4}[ -]){3}\d{4}\b"),
    "credential_assignment": re.compile(r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)\b\s*[:=]\s*\S+"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "openai_style_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "us_phone": re.compile(r"(?<!\d)(?:\+1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)"),
}

# Addresses that are documentation or role-based, not personal data.
ALLOWED_EMAILS = {"noreply@anthropic.com",
                  # Public office contacts from official pages (checked 2026-10-08)
                  "gwinnett@georgiasbdc.org", "info@atdc.org",
                  # LISC finalist sender, from the owner's confirmation email (2026-10-08)
                  "notifications@lisc.org",
                  # Public office contacts from official pages (checked 2026-10-12; planning/contacts.json)
                  "jennifer.white@innovate.gatech.edu", "susan.johnson@innovate.gatech.edu", "procurementhelp@doas.ga.gov", "support@grants.gov"}
ALLOWED_PHONES = {"(678) 985-6820", "1-800-375-1126", "800-375-1126", "404-524-5811", "1-800-388-2227", "800-388-2227", "800-829-4933", "1-800-591-8534", "800-591-8534", "800-827-5722", "800-827-5723", "833-572-0502", "866-433-4110", "(770) 962-7580", "(404) 894-3575", "404.894.2000", "+1 404.894.2000",
                  "770.822.8000", "800-906-9887", "888-227-7669",
                  "(404) 894-3512", "(404) 894-8122",  # GT APEX Atlanta office (APEX events page, 2026-10-08)
                  "(762) 499-0329",  # GT APEX Athens counselor (APEX application email, 2026-10-09)
                  "(706) 542-2762", "404-657-6000", "404-656-5514"}  # UGA SBDC training; GA DOAS (official pages, 2026-10-12)


def should_skip(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    return any(fnmatch.fnmatch(path.name.lower(), pat) for pat in SKIP_NAME_PATTERNS)


def blank_cents_columns(text: str) -> str:
    """Blank CSV cells in *_cents columns (integer money, not identifiers) before scanning.

    Only cells under a header ending in '_cents' are blanked; all other cells,
    including free text, are still scanned. Line numbers are preserved.
    """
    import csv, io
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return text
    cents = {i for i, h in enumerate(rows[0]) if h.endswith("_cents")}
    if not cents:
        return text
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(rows[0])
    for row in rows[1:]:
        w.writerow(["" if i in cents else cell for i, cell in enumerate(row)])
    return out.getvalue()


def scan_text(text: str):
    """Yield (line_no, kind, match) for every finding in text."""
    for line_no, line in enumerate(text.splitlines(), 1):
        for kind, rx in PATTERNS.items():
            for m in rx.finditer(line):
                if kind == "email" and m.group(0).lower() in ALLOWED_EMAILS:
                    continue
                if kind == "us_phone" and m.group(0).strip() in ALLOWED_PHONES:
                    continue
                yield line_no, kind, m.group(0)


def mask(value: str) -> str:
    return value[:2] + "*" * max(len(value) - 4, 1) + value[-2:] if len(value) > 4 else "****"


def scan_tree(root: Path, exclude=()):
    findings = []
    excluded = {(root / e).resolve() for e in exclude}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if not path.is_file() or should_skip(rel) or path.resolve() in excluded:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if path.suffix.lower() == ".csv":
            text = blank_cents_columns(text)
        for line_no, kind, match in scan_text(text):
            findings.append((str(rel), line_no, kind, mask(match)))
    return findings


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    root = Path(argv[0]) if argv else Path(".")
    # The scanner's own source and tests contain example patterns by design.
    findings = scan_tree(root, exclude=("badgr_funding/redact.py", "tests/test_redact.py"))
    for rel, line_no, kind, masked in findings:
        print(f"{rel}:{line_no}: {kind}: {masked}")
    print(f"{len(findings)} finding(s). Heuristic scan; see docs/PRIVACY.md for limitations.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
