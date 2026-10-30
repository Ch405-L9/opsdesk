"""Tests for metered API clients. No network: a fake session is injected."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from icp.budget import BudgetExceeded, BudgetLedger, ProviderQuota
from icp.providers import BraveSearch, HunterEmails, ProviderUnavailable, SerpApiSearch


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Records calls so tests can assert we hit the API exactly as often as billed."""
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload, self.status)


@pytest.fixture
def ledger(tmp_path):
    quotas = {
        "brave": ProviderQuota("brave", 1000, "requests", "BRAVE_API_KEY"),
        "serpapi": ProviderQuota("serpapi", 100, "searches", "SERPAPI_KEY"),
        "hunter": ProviderQuota("hunter", 50, "credits", "HUNTER_API_KEY"),
    }
    return BudgetLedger(tmp_path / "u.json", quotas, spend_posture=1.0, month="2026-10")


BRAVE_PAYLOAD = {"web": {"results": [
    {"title": "Billy Butler HVAC", "url": "https://billybutlerhvac.com/", "description": "HVAC repair"},
    {"title": "Cool Masters", "url": "https://coolmastershvac.com/", "description": "AC service"},
]}}


def test_client_without_key_is_unavailable_and_refuses_to_call(ledger):
    session = FakeSession(BRAVE_PAYLOAD)
    client = BraveSearch(ledger, api_key=None, session=session)
    assert client.available is False
    with pytest.raises(ProviderUnavailable):
        client.search("hvac lawrenceville ga")
    assert session.calls == [], "must not touch the network without a key"
    assert ledger.spent("brave") == 0, "must not bill for a call it never made"


def test_brave_search_returns_results_and_bills_one_request(ledger):
    session = FakeSession(BRAVE_PAYLOAD)
    client = BraveSearch(ledger, api_key="k", session=session)
    assert client.available is True

    results = client.search("hvac lawrenceville ga")
    assert [r["url"] for r in results] == ["https://billybutlerhvac.com/", "https://coolmastershvac.com/"]
    assert len(session.calls) == 1
    assert ledger.spent("brave") == 1


def test_brave_sends_key_in_header_not_query_string(ledger):
    session = FakeSession(BRAVE_PAYLOAD)
    BraveSearch(ledger, api_key="secret-key", session=session).search("x")
    url, kwargs = session.calls[0]
    assert "secret-key" not in url, "API key must never land in a URL"
    assert kwargs["headers"]["X-Subscription-Token"] == "secret-key"


def test_exhausted_budget_blocks_the_call_before_it_is_made(ledger):
    ledger.spend("brave", 1000)
    session = FakeSession(BRAVE_PAYLOAD)
    client = BraveSearch(ledger, api_key="k", session=session)
    assert client.available is False
    with pytest.raises(BudgetExceeded):
        client.search("x")
    assert session.calls == [], "budget check must precede the request"


def test_failed_request_is_still_billed(ledger):
    """Providers bill requests that reach them and then error, so we count on attempt."""
    session = FakeSession({}, status=500)
    client = BraveSearch(ledger, api_key="k", session=session)
    with pytest.raises(Exception):
        client.search("x")
    assert ledger.spent("brave") == 1


def test_serpapi_extracts_organic_results(ledger):
    payload = {"organic_results": [
        {"title": "A Roofing", "link": "https://aroofing.com/", "snippet": "roofs"},
        {"title": "B Roofing", "link": "https://broofing.com/", "snippet": "more roofs"},
    ]}
    session = FakeSession(payload)
    results = SerpApiSearch(ledger, api_key="k", session=session).search("roofing duluth ga")
    assert [r["url"] for r in results] == ["https://aroofing.com/", "https://broofing.com/"]
    assert ledger.spent("serpapi") == 1


def test_hunter_domain_search_bills_per_call_and_parses_emails(ledger):
    payload = {"data": {"emails": [
        {"value": "owner@example.com", "confidence": 94, "first_name": "Pat", "last_name": "Doe", "position": "Owner"},
        {"value": "info@example.com", "confidence": 71, "first_name": None, "last_name": None, "position": None},
    ]}}
    session = FakeSession(payload)
    contacts = HunterEmails(ledger, api_key="k", session=session).domain_search("example.com")
    assert contacts[0]["email"] == "owner@example.com"
    assert contacts[0]["confidence"] == 94
    assert ledger.spent("hunter") == 1


def test_hunter_respects_its_tiny_allowance(ledger):
    session = FakeSession({"data": {"emails": []}})
    client = HunterEmails(ledger, api_key="k", session=session)
    for _ in range(50):
        client.domain_search("example.com")
    assert ledger.remaining("hunter") == 0
    with pytest.raises(BudgetExceeded):
        client.domain_search("another.com")
    assert len(session.calls) == 50, "the 51st call must never be sent"
