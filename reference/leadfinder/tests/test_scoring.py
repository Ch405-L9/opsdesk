"""Tests for the multi-axis lead scorer."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from icp.scoring import disqualify, score_lead, AXES, vertical_tier

def L(**kw):
    base = dict(name="Acme Med Spa", website="https://acme.com", has_website=True,
                phone="(770) 555-0100", rating=4.8, review_count=200,
                status="OPERATIONAL", place_type="spa", vertical="med_spa")
    base.update(kw); return base

def A(**kw):
    base = dict(performance=55, seo=80, accessibility=70, best_practices=75,
                lcp_ms=3000, has_field_data=False)
    base.update(kw); return base

# ---- disqualifiers ----------------------------------------------------------
def test_franchise_location_url_is_disqualified():
    assert disqualify(L(website="https://mightydogroofing.com/north-atlanta-ga/")) == "FRANCHISE_URL_PATTERN"

def test_manufacturer_directory_is_disqualified():
    assert disqualify(L(website="https://www.gaf.com/en-us/roofing-contractors/x")) == "MANUFACTURER_OR_DIRECTORY"

def test_captive_agent_is_disqualified():
    assert disqualify(L(website="https://agents.statefarm.com/j-doe")) == "CAPTIVE_AGENT"

def test_closed_business_is_disqualified():
    assert disqualify(L(status="CLOSED_PERMANENTLY")) == "DORMANT"

def test_normal_independent_business_is_not_disqualified():
    assert disqualify(L()) is None

def test_no_website_is_never_disqualified():
    """No website is the best signal there is - it must survive the filter."""
    assert disqualify(L(website=None, has_website=False)) is None

# ---- need -------------------------------------------------------------------
def test_no_website_maxes_need():
    s = score_lead(L(website=None, has_website=False), audit=None)
    assert s["need"] >= 90

def test_broken_site_scores_higher_need_than_fast_site():
    slow = score_lead(L(), A(performance=20, lcp_ms=7000, seo=40))
    fast = score_lead(L(), A(performance=95, lcp_ms=1500, seo=95))
    assert slow["need"] > fast["need"] + 30

def test_plain_http_adds_need_only_when_measured():
    """Need must not inflate from an unverified URL prefix."""
    secure = score_lead(L(), A(final_url="https://acme.com/"))
    insecure = score_lead(L(), A(final_url="http://acme.com/"))
    assert insecure["need"] > secure["need"]
    unverified = score_lead(L(website="http://acme.com"), A())
    assert unverified["need"] == score_lead(L(website="https://acme.com"), A())["need"]

# ---- ability ----------------------------------------------------------------
def test_more_reviews_means_more_ability():
    big = score_lead(L(review_count=800), A())
    small = score_lead(L(review_count=3), A())
    assert big["ability"] > small["ability"]

def test_high_tier_vertical_beats_low_tier():
    """Tier now drives fit only - it used to be double counted in ability too,
    giving it an effective weight of ~0.60 instead of the documented 0.25."""
    spa = score_lead(L(vertical="med_spa"), A())
    salon = score_lead(L(vertical="hair_salon"), A())
    assert spa["fit"] > salon["fit"]
    assert spa["priority"] > salon["priority"]
    assert spa["ability"] == salon["ability"]

# ---- fit / reach ------------------------------------------------------------
def test_missing_phone_lowers_reach():
    with_p = score_lead(L(phone="(770) 555-0100"), A())
    without = score_lead(L(phone=""), A())
    assert without["reach"] < with_p["reach"]

def test_vertical_tier_lookup_is_case_insensitive_and_defaults():
    assert vertical_tier("MED_SPA") == vertical_tier("med_spa")
    assert vertical_tier("totally_unknown_vertical") is not None

# ---- priority ---------------------------------------------------------------
def test_high_need_no_ability_scores_low():
    """A church: maximum need, no budget. The old bool(signals) ranked it prime."""
    church = score_lead(L(vertical="church", review_count=2, website=None, has_website=False), None)
    good = score_lead(L(vertical="med_spa", review_count=300), A(performance=35))
    assert church["priority"] < good["priority"]

def test_all_axes_present_and_bounded():
    s = score_lead(L(), A())
    for axis in AXES:
        assert 0 <= s[axis] <= 100, (axis, s[axis])
    assert 0 <= s["priority"] <= 100

def test_disqualified_lead_returns_zero_priority_and_reason():
    s = score_lead(L(website="https://mightydogroofing.com/north-atlanta-ga/"), A())
    assert s["priority"] == 0
    assert s["disqualified"] == "FRANCHISE_URL_PATTERN"

def test_audit_none_does_not_crash():
    s = score_lead(L(), None)
    assert s["priority"] >= 0
