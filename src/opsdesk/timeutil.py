"""Time-zone aware helpers. Dates are stored as ISO strings; follow-ups are date-only."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

DEFAULT_TZ = "America/New_York"


def zone(name: str | None = None) -> ZoneInfo:
    return ZoneInfo(name or DEFAULT_TZ)


def now(tz: str | None = None) -> dt.datetime:
    return dt.datetime.now(zone(tz))


def now_iso(tz: str | None = None) -> str:
    return now(tz).isoformat(timespec="seconds")


def today(tz: str | None = None) -> dt.date:
    return now(tz).date()


def parse_date(value: object) -> dt.date | None:
    """Accept date, datetime, or 'YYYY-MM-DD...' strings; anything else is None."""
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def parse_when(text: str, tz: str | None = None) -> dt.date:
    """Parse follow-up shorthands: YYYY-MM-DD, today, tomorrow, +3d, +2w, mon..sun."""
    t = text.strip().lower()
    base = today(tz)
    if t in {"today", "now"}:
        return base
    if t == "tomorrow":
        return base + dt.timedelta(days=1)
    if t.startswith("+") and t[-1] in "dw" and t[1:-1].isdigit():
        n = int(t[1:-1])
        return base + dt.timedelta(days=n * (7 if t[-1] == "w" else 1))
    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    if t[:3] in days:
        delta = (days.index(t[:3]) - base.weekday()) % 7 or 7
        return base + dt.timedelta(days=delta)
    parsed = parse_date(t)
    if parsed is None:
        raise ValueError(f"Unrecognized date {text!r}. Use YYYY-MM-DD, today, tomorrow, +3d, +2w or a weekday.")
    return parsed
