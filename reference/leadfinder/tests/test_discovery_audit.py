"""Tests for Places discovery and PSI audit parsing. No network: fake sessions."""
import pathlib, sys
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from icp.budget import BudgetLedger, ProviderQuota
from icp.discovery import PlacesDiscovery, parse_places
from icp.audit import PsiAudit, parse_psi


class FakeResp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status
    def json(self): return self._p
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(f"HTTP {self.status_code}")

class FakeSession:
    def __init__(self, payload, status=200):
        self.payload, self.status, self.calls = payload, status, []
    def post(self, url, **kw):
        self.calls.append((url, kw)); return FakeResp(self.payload, self.status)
    def get(self, url, **kw):
        self.calls.append((url, kw)); return FakeResp(self.payload, self.status)

@pytest.fixture
def ledger(tmp_path):
    q = {"places": ProviderQuota("places", 1000, "requests", "GOOGLE_PLACES_API_KEY"),
         "psi": ProviderQuota("psi", 25000, "requests", "GOOGLE_PSI_API_KEY")}
    return BudgetLedger(tmp_path / "u.json", q, spend_posture=1.0, month="2026-10")

PLACES_PAYLOAD = {"places": [
    {"displayName": {"text": "MadEmEl Medical Aesthetics"}, "websiteUri": "https://mademelmedspa.com/",
     "formattedAddress": "1 A St, Lawrenceville, GA", "rating": 4.9, "userRatingCount": 120},
    {"displayName": {"text": "Bella Forever Med Spa"},
     "formattedAddress": "2 B St, Lawrenceville, GA", "rating": 4.2, "userRatingCount": 8},
]}

def test_parse_places_keeps_business_with_no_website():
    """A business with NO website is the strongest need signal - never drop it."""
    rows = parse_places(PLACES_PAYLOAD)
    assert len(rows) == 2
    noweb = [r for r in rows if r["website"] is None]
    assert len(noweb) == 1
    assert noweb[0]["name"] == "Bella Forever Med Spa"
    assert noweb[0]["has_website"] is False

def test_parse_places_extracts_fields():
    rows = parse_places(PLACES_PAYLOAD)
    r = rows[0]
    assert r["name"] == "MadEmEl Medical Aesthetics"
    assert r["website"] == "https://mademelmedspa.com/"
    assert r["rating"] == 4.9 and r["review_count"] == 120
    assert r["has_website"] is True

def test_parse_places_empty_payload():
    assert parse_places({}) == []

def test_places_discovery_bills_once_and_sends_key_in_header(ledger):
    s = FakeSession(PLACES_PAYLOAD)
    d = PlacesDiscovery(ledger, api_key="k", session=s)
    rows = d.search("med spa", "Lawrenceville GA")
    assert len(rows) == 2
    assert ledger.spent("places") == 1
    url, kw = s.calls[0]
    assert "k" not in url
    assert kw["headers"]["X-Goog-Api-Key"] == "k"
    assert "places.googleapis.com" in url

PSI_PAYLOAD = {"lighthouseResult": {"categories": {
    "performance": {"score": 0.42}, "seo": {"score": 0.8}, "accessibility": {"score": 0.61},
}, "audits": {"largest-contentful-paint": {"numericValue": 5200.0}}},
 "loadingExperience": {"metrics": {}}}

def test_parse_psi_scales_scores_to_100():
    a = parse_psi(PSI_PAYLOAD)
    assert a["performance"] == 42
    assert a["seo"] == 80
    assert a["accessibility"] == 61
    assert a["lcp_ms"] == 5200

def test_parse_psi_handles_missing_categories():
    a = parse_psi({"lighthouseResult": {"categories": {}}})
    assert a["performance"] is None
    assert a["lcp_ms"] is None

def test_psi_audit_bills_and_returns_scores(ledger):
    s = FakeSession(PSI_PAYLOAD)
    a = PsiAudit(ledger, api_key="k", session=s).audit("https://example.com")
    assert a["performance"] == 42
    assert ledger.spent("psi") == 1

def test_psi_audit_without_key_is_unavailable(ledger):
    from icp.providers import ProviderUnavailable
    s = FakeSession(PSI_PAYLOAD)
    a = PsiAudit(ledger, api_key=None, session=s)
    assert a.available is False
    with pytest.raises(ProviderUnavailable):
        a.audit("https://example.com")
    assert s.calls == []
