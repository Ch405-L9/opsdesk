import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from opsdesk.leads.painpoints import band, headline_pain, pain_points, scores_worst_to_best


def L(**kw):
    b = dict(name="X", website="https://x.com", has_website=True, vertical="med_spa",
             review_count=100); b.update(kw); return b
def A(**kw):
    b = dict(performance=55, seo=85, accessibility=80, best_practices=90, lcp_ms=3000); b.update(kw); return b

def test_bands_match_google_thresholds():
    assert band(31) == "poor"; assert band(55) == "needs work"
    assert band(95) == "good";  assert band(None) == "unknown"

def test_no_website_is_top_pain_and_short_circuits():
    p = pain_points(L(has_website=False, website=None), None)
    assert len(p) == 1 and p[0]["code"] == "NO_WEBSITE"
    assert "2,500" in p[0]["est_value"]

def test_http_site_flags_no_ssl_only_when_measured():
    """Changed 2026-10-27: a bare http:// in the Places URL is NOT evidence.
    9 of 10 live leads stored as http:// actually served HTTPS."""
    unverified = [x["code"] for x in pain_points(L(website="http://x.com"), A())]
    assert "NO_SSL" not in unverified
    measured = [x["code"] for x in pain_points(L(website="http://x.com"),
                                               A(final_url="http://x.com/"))]
    assert "NO_SSL" in measured

def test_pains_sorted_worst_first():
    p = pain_points(L(), A(performance=20, seo=40, best_practices=85))
    assert p == sorted(p, key=lambda x: -x["severity"])
    assert headline_pain(p)["severity"] >= p[-1]["severity"]

def test_accessibility_severity_higher_for_medical_verticals():
    med = pain_points(L(vertical="dentist"), A(accessibility=60))
    gym = pain_points(L(vertical="gym"), A(accessibility=60))
    m = [x for x in med if x["code"] == "ACCESSIBILITY"][0]
    g = [x for x in gym if x["code"] == "ACCESSIBILITY"][0]
    assert m["severity"] > g["severity"]
    assert "legal advice" in m["angle"]

def test_good_site_has_no_pains():
    assert pain_points(L(), A(performance=95, seo=95, accessibility=95, best_practices=95, lcp_ms=1200)) == []

def test_never_claims_speed_improves_ranking():
    for p in pain_points(L(), A(performance=20)):
        blob = (p["angle"] + p["evidence"]).lower()
        assert not ("rank" in blob and "improve" in blob and "speed" in blob)

def test_evidence_always_contains_a_number():
    for p in pain_points(L(website="http://x.com"), A(performance=31, seo=40, accessibility=50)):
        assert any(c.isdigit() for c in p["evidence"]), p["code"]

def test_scores_worst_to_best_ordering():
    s = scores_worst_to_best(A(performance=30, seo=90, accessibility=60, best_practices=70))
    assert [k for k, _ in s] == ["performance", "accessibility", "best practices", "SEO"]

def test_scores_worst_to_best_handles_no_audit():
    assert scores_worst_to_best(None) == []
