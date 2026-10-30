import datetime as dt

import pytest

from opsdesk import timeutil
from opsdesk.workbench import get_item, list_items, resolve_key, upsert_item, workbench
from opsdesk.workflow import (
    WorkflowError,
    add_note,
    follow,
    mark_done,
    set_fields,
    snooze,
    today_view,
)


def test_upsert_insert_unchanged_updated_and_default_workflow(paths):
    with workbench(paths) as conn:
        assert upsert_item(conn, "lead:a.example", {"name": "A"}) == "inserted"
        assert upsert_item(conn, "lead:a.example", {"name": "A"}) == "unchanged"
        assert upsert_item(conn, "lead:a.example", {"name": "A2"}) == "updated"
        item = get_item(conn, "lead:a.example")
        assert item["name"] == "A2" and item["status"] == "new" and item["priority"] == "normal"


def test_refetch_never_overwrites_user_workflow(paths):
    with workbench(paths) as conn:
        upsert_item(conn, "bid:usaspending:1", {"recipient": "X", "sub_agency": "Navy"})
        set_fields(conn, "bid:usaspending:1", status="pursue", priority="high", notes="mine")
        upsert_item(conn, "bid:usaspending:1", {"recipient": "X", "sub_agency": "Navy", "amount": 5})
        item = get_item(conn, "bid:usaspending:1")
    assert (item["status"], item["priority"], item["notes"], item["amount"]) == ("pursue", "high", "mine", 5)


def test_invalid_status_and_fields_rejected(paths):
    with workbench(paths) as conn:
        upsert_item(conn, "job:manual:1", {"title": "Dev", "company": "Co"})
        with pytest.raises(WorkflowError):
            set_fields(conn, "job:manual:1", status="won")  # not a job status
        with pytest.raises(WorkflowError):
            set_fields(conn, "job:manual:1", payload="x")
        with pytest.raises(WorkflowError):
            set_fields(conn, "job:manual:1", followup_date="next tuesday-ish")


@pytest.mark.parametrize("value,expected", [("☑", 1), ("TRUE", 1), ("x", 1), ("yes", 1), ("☐", 0), ("", 0), (True, 1), (False, 0)])
def test_checkbox_values(paths, value, expected):
    with workbench(paths) as conn:
        upsert_item(conn, "lead:b.example", {"name": "B"})
        set_fields(conn, "lead:b.example", done=value)
        assert get_item(conn, "lead:b.example")["done"] is bool(expected)


def test_today_buckets_notes_done_and_snooze(paths, monkeypatch):
    fixed = dt.date(2026, 3, 8)  # US DST starts this day
    monkeypatch.setattr(timeutil, "today", lambda tz=None: fixed)
    with workbench(paths) as conn:
        for key, delta in (("lead:o.example", -1), ("lead:t.example", 0), ("lead:u.example", 3), ("lead:f.example", 30)):
            upsert_item(conn, key, {"name": key})
            follow(conn, key, fixed + dt.timedelta(days=delta), "call")
        upsert_item(conn, "lead:closed.example", {"name": "closed"})
        follow(conn, "lead:closed.example", fixed, "x")
        set_fields(conn, "lead:closed.example", status="lost")
        view = today_view(conn)
        assert [i["wb_key"] for i in view["overdue"]] == ["lead:o.example"]
        assert [i["wb_key"] for i in view["today"]] == ["lead:t.example"]
        assert [i["wb_key"] for i in view["upcoming"]] == ["lead:u.example"]
        mark_done(conn, "lead:o.example")
        assert today_view(conn)["overdue"] == []
        add_note(conn, "lead:t.example", "first")
        add_note(conn, "lead:t.example", "second")
        notes = get_item(conn, "lead:t.example")["notes"]
        assert notes.splitlines() == ["[2026-03-08] first", "[2026-03-08] second"]
        assert snooze(conn, "lead:t.example", 3) == dt.date(2026, 3, 11)


def test_parse_when_shorthands(monkeypatch):
    monkeypatch.setattr(timeutil, "today", lambda tz=None: dt.date(2026, 10, 30))  # a Friday
    assert timeutil.parse_when("+3d") == dt.date(2026, 11, 2)
    assert timeutil.parse_when("+2w") == dt.date(2026, 11, 13)
    assert timeutil.parse_when("tomorrow") == dt.date(2026, 10, 31)
    assert timeutil.parse_when("mon") == dt.date(2026, 11, 2)
    assert timeutil.parse_when("fri") == dt.date(2026, 11, 6)
    assert timeutil.parse_when("2026-12-01") == dt.date(2026, 12, 1)
    with pytest.raises(ValueError):
        timeutil.parse_when("someday")


def test_resolve_key_by_fragment(paths):
    with workbench(paths) as conn:
        upsert_item(conn, "lead:a.example", {"name": "Alpha Dental"})
        upsert_item(conn, "lead:b.example", {"name": "Alpha Roofing"})
        assert resolve_key(conn, "dental") == "lead:a.example"
        with pytest.raises(KeyError, match="2 items"):
            resolve_key(conn, "alpha")
        with pytest.raises(KeyError):
            resolve_key(conn, "nothing")
        assert len(list_items(conn, "lead")) == 2
