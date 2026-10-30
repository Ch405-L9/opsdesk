import pytest

from opsdesk.leads import service
from opsdesk.workbench import get_item, workbench


class FakeResp:
    def __init__(self, payload):
        self.payload, self.status_code = payload, 200

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self):
        self.calls = 0

    def post(self, url, **kw):
        self.calls += 1
        return FakeResp({"places": [{"displayName": {"text": "Real Dental"}, "websiteUri": "https://realdental.example",
                                     "formattedAddress": "1 Main St", "rating": 4.5, "userRatingCount": 40,
                                     "nationalPhoneNumber": "(555) 555-0101", "businessStatus": "OPERATIONAL",
                                     "primaryType": "dentist"}]})


def test_demo_without_key_is_free_and_labeled(paths):
    result = service.find(paths, "dentists in Austin TX")
    assert result.source.startswith("demo") and not result.spent_call
    assert all(r["demo"] for r in result.rows) and len({r["key"] for r in result.rows}) == len(result.rows)


def test_api_requires_confirmation_then_caches(paths, monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")
    assert service.plan_find(paths, "dentists in Austin TX")["cost_calls"] == 1
    with pytest.raises(PermissionError):
        service.find(paths, "dentists in Austin TX")
    session = FakeSession()
    first = service.find(paths, "dentists in Austin TX", confirmed=True, session=session)
    assert first.spent_call and session.calls == 1
    plan = service.plan_find(paths, "dentists in Austin TX")
    assert plan["mode"] == "cache" and plan["cost_calls"] == 0 and plan["remaining"] == plan["usable"] - 1
    second = service.find(paths, "dentists in Austin TX", confirmed=True, session=session)
    assert session.calls == 1 and "cache" in second.source


def test_lead_key_prefers_host():
    assert service.lead_key({"website": "https://www.Foo.example/path"}) == "lead:foo.example"
    a = service.lead_key({"name": "X", "phone": "(555) 555-0100"})
    assert a.startswith("lead:n-") and a == service.lead_key({"name": "x", "phone": "555.555.0100"})


def test_draft_is_honest_without_an_audit_and_signed_from_profile(paths):
    result = service.find(paths, "dentists in Austin TX", demo=True)
    key = next(r["key"] for r in result.rows if r.get("website"))
    d = service.draft(paths, key)
    assert "free Google Lighthouse test" in d["body"] and "Sam Lee" in d["body"] and "Sam Lee" in d["call_opener"]
    assert "came back clean" not in d["body"]
    with workbench(paths) as conn:
        assert get_item(conn, key)["status"] == "new"


def test_lead_without_website_cannot_be_audited(paths):
    result = service.find(paths, "roofers in Austin TX", demo=True)
    key = next(r["key"] for r in result.rows if not r.get("website"))
    with pytest.raises(ValueError):
        service.audit(paths, key, confirmed=True)
