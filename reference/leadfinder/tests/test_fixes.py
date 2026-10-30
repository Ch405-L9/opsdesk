"""Tests for the five lead-quality fixes (2026-10-27 advisor review)."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from icp.scoring import _ability, _need, score_lead
from icp.painpoints import pain_points
from icp.audit import parse_psi
from icp.store import Store, lead_key

def L(**kw):
    b = dict(name="X", website="http://x.com", has_website=True, vertical="med_spa",
             review_count=100, rating=4.8, status="OPERATIONAL", phone="1", address="a")
    b.update(kw); return b

# ---- FIX 1: SSL must come from a measured final URL, never a prefix --------
def test_parse_psi_captures_final_url():
    a = parse_psi({"lighthouseResult": {"categories": {}, "finalUrl": "https://x.com/"}})
    assert a["final_url"] == "https://x.com/"

def test_no_ssl_not_claimed_when_site_redirects_to_https():
    """9 of 10 live leads stored as http:// actually serve HTTPS."""
    audit = {"performance": 80, "seo": 90, "accessibility": 90, "best_practices": 90,
             "lcp_ms": 2000, "final_url": "https://x.com/"}
    assert "NO_SSL" not in [p["code"] for p in pain_points(L(), audit)]

def test_no_ssl_claimed_only_when_final_url_is_really_http():
    audit = {"performance": 80, "seo": 90, "accessibility": 90, "best_practices": 90,
             "lcp_ms": 2000, "final_url": "http://x.com/"}
    assert "NO_SSL" in [p["code"] for p in pain_points(L(), audit)]

def test_no_ssl_never_claimed_without_evidence():
    """No audit and no resolved URL -> make no claim at all."""
    assert "NO_SSL" not in [p["code"] for p in pain_points(L(), None)]

def test_need_does_not_inflate_from_unverified_http_prefix():
    bare = _need(L(), None)
    resolved = _need(L(final_url="https://x.com/"), None)
    assert bare == resolved, "an unverified http:// prefix must not add need points"

def test_need_adds_points_for_verified_insecure_site():
    secure = _need(L(), {"performance": 80, "seo": 90, "final_url": "https://x.com/"})
    insecure = _need(L(), {"performance": 80, "seo": 90, "final_url": "http://x.com/"})
    assert insecure > secure

# ---- FIX 4: vertical tier must not be double counted ----------------------
def test_ability_no_longer_contains_vertical_tier():
    a_tier = _ability(L(vertical="med_spa", review_count=100))
    d_tier = _ability(L(vertical="hair_salon", review_count=100))
    assert a_tier == d_tier, "tier belongs to fit only, not ability"

def test_ability_still_tracks_business_size():
    assert _ability(L(review_count=800)) > _ability(L(review_count=5))

def test_ability_stays_in_range():
    assert 0 <= _ability(L(review_count=0, rating=0)) <= 100
    assert 0 <= _ability(L(review_count=5000, rating=5.0, multi_location=True)) <= 100

def test_tier_still_drives_fit():
    spa = score_lead(L(vertical="med_spa"), None)
    salon = score_lead(L(vertical="hair_salon"), None)
    assert spa["fit"] > salon["fit"]
    assert spa["priority"] > salon["priority"]

# ---- FIX 2: stable key + has_website updates -------------------------------
def test_lead_key_ignores_utm_and_www():
    a = lead_key({"website": "https://www.duluthdentalsmiles.com/?utm_source=google&utm_campaign=gmb"})
    b = lead_key({"website": "http://duluthdentalsmiles.com/"})
    assert a == b == "duluthdentalsmiles.com"

def test_lead_key_falls_back_to_name():
    assert lead_key({"website": None, "name": "Bella Forever Med Spa"}) == "bella forever med spa"

def test_utm_change_does_not_create_duplicate(tmp_path):
    s = Store(tmp_path / "t.db")
    s.upsert_leads([{"name": "A", "website": "https://a.com/?utm_source=x", "priority": 50, "has_website": True}])
    s.upsert_leads([{"name": "A", "website": "https://a.com/?utm_source=DIFFERENT", "priority": 50, "has_website": True}])
    assert s.count_leads() == 1

def test_has_website_is_updated_on_conflict(tmp_path):
    s = Store(tmp_path / "t.db")
    s.upsert_leads([{"name": "A", "website": None, "has_website": False, "priority": 90}])
    s.upsert_leads([{"name": "A", "website": "https://a.com", "has_website": True, "priority": 60}])
    row = s.conn.execute("SELECT has_website, website FROM leads").fetchone()
    assert row["has_website"] == 1, "stale has_website causes 'you have no website' emails"
    assert row["website"] == "https://a.com"

# ---- FIX 5: never cache an empty result for 14 days ------------------------
def test_empty_search_is_not_cached(tmp_path):
    s = Store(tmp_path / "t.db")
    s.put_search("nothing", "nowhere", [])
    assert s.cached_search("nothing", "nowhere") is None, \
        "an empty result cached for 14 days reads as 'no businesses exist'"

def test_nonempty_search_is_cached(tmp_path):
    s = Store(tmp_path / "t.db")
    s.put_search("med spa", "lville", [{"name": "A"}])
    assert s.cached_search("med spa", "lville") == [{"name": "A"}]
