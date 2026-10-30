"""Parse a job "capture": a small Markdown file the user pastes a posting into.

Format (keys are case-insensitive; everything after a line with only '---' is the description):

    title: Web Developer
    company: Acme Co
    url: https://jobs.example.com/123
    location: Remote, US
    arrangement: remote | hybrid | onsite
    employment: full_time | part_time | contract | gig
    salary_min: 70000
    salary_max: 90000
    closes: 2026-11-30
    clearance: none
    required:
    - Python
    - React
    preferred:
    - AWS
    ---
    Paste the posting text here.
"""

from __future__ import annotations

import hashlib
import re
import textwrap
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from opsdesk import timeutil

LIST_KEYS = {"required", "preferred"}
ARRANGEMENTS = {"remote", "hybrid", "onsite", "unknown"}
EMPLOYMENT = {"full_time", "part_time", "contract", "gig", "unknown"}
TEMPLATE = textwrap.dedent(__doc__.split("Format", 1)[1].split("\n\n", 1)[1]).strip() + "\n" if __doc__ else ""


class CaptureError(ValueError):
    pass


def _money(value: str) -> int | None:
    digits = re.sub(r"[^\d.]", "", value or "")
    if not digits:
        return None
    number = float(digits)
    if re.search(r"\d\s*k\b", value.lower()):
        number *= 1000
    return int(number)


def clean_url(url: str) -> str:
    """Drop tracking query strings and fragments; keep scheme/host/path."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"}:
        raise CaptureError(f"url must start with http(s): {url!r}")
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, "", ""))


def parse(text: str) -> dict[str, Any]:
    head, _, description = text.partition("\n---")
    data: dict[str, Any] = {"required": [], "preferred": []}
    current: str | None = None
    for raw in head.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-", "*")) and current in LIST_KEYS:
            value = line[1:].strip()
            if value:
                data[current].append(value)
            continue
        if ":" not in line:
            raise CaptureError(f"Line is not 'key: value': {line!r}")
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower().replace(" ", "_")
        current = key
        if key in LIST_KEYS:
            data[key] += [v.strip() for v in value.split(",") if v.strip()] if value else []
        else:
            data[key] = value
    if not data.get("title") or not data.get("company"):
        raise CaptureError("A capture needs at least 'title:' and 'company:'.")
    data["url"] = clean_url(data.get("url", ""))
    data["arrangement"] = (data.get("arrangement") or "unknown").lower().replace("-", "").replace("on site", "onsite")
    if data["arrangement"] not in ARRANGEMENTS:
        raise CaptureError(f"arrangement must be one of {sorted(ARRANGEMENTS)}")
    data["employment"] = (data.get("employment") or "unknown").lower().replace("-", "_").replace(" ", "_")
    if data["employment"] not in EMPLOYMENT:
        raise CaptureError(f"employment must be one of {sorted(EMPLOYMENT)}")
    for key in ("salary_min", "salary_max"):
        data[key] = _money(str(data.get(key, "")))
    if data.get("closes"):
        closes = timeutil.parse_date(data["closes"])
        if closes is None:
            raise CaptureError("closes must be YYYY-MM-DD")
        data["closes"] = closes.isoformat()
    data["description"] = description.strip()
    data["snapshot_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    return data


def job_key(job: dict[str, Any]) -> str:
    if job.get("url"):
        parts = urlsplit(job["url"])
        digest = hashlib.sha1(f"{parts.netloc}{parts.path}".encode()).hexdigest()[:12]
        return f"job:{parts.netloc.removeprefix('www.')}:{digest}"
    basis = f"{job['company']}|{job['title']}".lower()
    return "job:manual:" + hashlib.sha1(basis.encode()).hexdigest()[:12]
