"""Network half: fetch public USAspending award data (no API key). Called only after confirmation."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from opsdesk.bids.rank import CERT_SET_ASIDE, SB_SET_ASIDE

API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
FIELDS = ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Awarding Sub Agency",
          "Start Date", "End Date", "generated_internal_id", "NAICS"]
TAGS: dict[str, tuple[str, ...] | None] = {"sb_set_aside": SB_SET_ASIDE, "cert_required": CERT_SET_ASIDE, "any": None}


def request_body(tag: str, start: str, end: str, page: int, naics: list[str], state: str) -> dict[str, Any]:
    filters: dict[str, Any] = {
        "award_type_codes": ["A", "B", "C", "D"],
        "naics_codes": {"require": list(naics)},
        "time_period": [{"start_date": start, "end_date": end}],
    }
    if state:
        filters["place_of_performance_locations"] = [{"country": "USA", "state": state.upper()}]
    codes = TAGS[tag]
    if codes:
        filters["set_aside_type_codes"] = list(codes)
    return {"filters": filters, "fields": FIELDS, "limit": 100, "page": page, "sort": "End Date", "order": "desc"}


def _post(body: dict[str, Any]) -> dict[str, Any]:
    response = httpx.post(API, json=body, timeout=90, headers={"User-Agent": "OpsDesk/1.0 (local research tool)"})
    response.raise_for_status()
    return dict(response.json())


def fetch(tag: str, start: str, end: str, naics: list[str], state: str, *, max_pages: int = 25,
          post: Callable[[dict[str, Any]], dict[str, Any]] = _post, pause: float = 0.5) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    page = 1
    while page <= max_pages:
        data = post(request_body(tag, start, end, page, naics, state))
        rows += data.get("results", [])
        if not (data.get("page_metadata") or {}).get("hasNext"):
            break
        page += 1
        if pause:
            time.sleep(pause)
    return rows, page
