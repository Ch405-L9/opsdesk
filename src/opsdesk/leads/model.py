"""Shared lead data helpers and safe synthetic demo records."""

from __future__ import annotations

import re
from typing import Any

from opsdesk.leads.scoring import score_lead


def parse_query(query: str, default_location: str = "") -> tuple[str, str]:
    """Split a simple `<industry> in <location>` query without guessing a city."""
    parts = re.split(r"\s+in\s+", query.strip(), maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return query.strip(), default_location.strip()


def demo_leads(industry: str, location: str) -> list[dict[str, Any]]:
    """Return explicitly synthetic demo records; domains are reserved examples."""
    label = industry.strip().title() or "Local Service"
    city = location.strip() or "your area"
    raw: list[dict[str, Any]] = [
        {
            "name": f"{label} Studio Example",
            "website": f"https://{re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')}-studio.example.test",
            "has_website": True,
            "address": f"{city} — synthetic demo location",
            "phone": "",
            "rating": 4.7,
            "review_count": 83,
            "status": "OPERATIONAL",
            "vertical": industry.strip().lower().replace(" ", "_"),
            "place_type": label,
            "demo": True,
        },
        {
            "name": f"{label} Works Sample",
            "website": None,
            "has_website": False,
            "address": f"{city} — synthetic demo location",
            "phone": "",
            "rating": 4.4,
            "review_count": 29,
            "status": "OPERATIONAL",
            "vertical": industry.strip().lower().replace(" ", "_"),
            "place_type": label,
            "demo": True,
        },
    ]
    return [{**lead, **score_lead(lead)} for lead in raw]
