"""Date/time helpers. Local timezone is America/New_York; date-only values stay date-only."""
import datetime as dt
from zoneinfo import ZoneInfo

LOCAL_TZ_NAME = "America/New_York"
LOCAL_TZ = ZoneInfo(LOCAL_TZ_NAME)


def now():
    return dt.datetime.now(LOCAL_TZ)


def now_iso():
    return now().isoformat(timespec="seconds")


def today():
    return now().date()


def parse_date(s):
    return dt.date.fromisoformat(s) if s else None


def months_between(start, end):
    """Whole calendar months elapsed from start to end (end-exclusive day rule)."""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months


def add_months(d, months):
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    for day in (d.day, 30, 29, 28):
        try:
            return dt.date(year, month, day)
        except ValueError:
            continue
    raise ValueError(d)


def history_gate_date(formation, min_months):
    """First date on which the business has existed min_months full months."""
    return add_months(formation, min_months) if formation and min_months is not None else None


def deadline_display(deadline_date, deadline_time=None, deadline_tz=None, rolling="unknown"):
    """Human-readable deadline. Missing deadline never reads as rolling unless confirmed."""
    if not deadline_date:
        return "Rolling (confirmed)" if rolling == "yes" else "Unknown deadline"
    if not deadline_time:
        return f"{deadline_date} (date only; cutoff time not published)"
    tz = deadline_tz or LOCAL_TZ_NAME
    local = deadline_local(deadline_date, deadline_time, tz)
    note = "" if tz == LOCAL_TZ_NAME else f" ({deadline_date} {deadline_time} {tz})"
    return f"{local.strftime('%Y-%m-%d %H:%M %Z')}{note}"


def deadline_local(deadline_date, deadline_time, tz_name):
    """Convert a sponsor-timezone deadline to America/New_York, DST-aware."""
    d = dt.date.fromisoformat(deadline_date)
    h, m = (int(x) for x in deadline_time.split(":"))
    aware = dt.datetime(d.year, d.month, d.day, h, m, tzinfo=ZoneInfo(tz_name))
    return aware.astimezone(LOCAL_TZ)


def days_until(deadline_date, ref=None):
    if not deadline_date:
        return None
    return (dt.date.fromisoformat(deadline_date) - (ref or today())).days


def is_stale(checked_at, max_age_days, ref=None):
    """A source never checked, or checked more than max_age_days ago, is stale."""
    if not checked_at:
        return True
    checked = dt.date.fromisoformat(checked_at[:10])
    return ((ref or today()) - checked).days > max_age_days
