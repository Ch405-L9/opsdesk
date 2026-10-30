import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from opsdesk.leads.outreach import call_opener, cold_email
from opsdesk.leads.painpoints import pain_points
from opsdesk.leads.providers import candidate_emails


def L(**kw):
    b = dict(name="Bella Med Spa", website="https://bella.example", has_website=True,
             vertical="med_spa", review_count=163, rating=4.7); b.update(kw); return b
def A(**kw):
    b = dict(performance=31, seo=70, accessibility=55, best_practices=85, lcp_ms=6200); b.update(kw); return b

def test_email_cites_the_measured_score():
    lead, audit = L(), A()
    e = cold_email(lead, audit, pain_points(lead, audit))
    assert "31" in e["body"]
    assert "Lighthouse" in e["body"]

def test_no_website_email_leads_with_reviews():
    lead = L(has_website=False, website=None)
    e = cold_email(lead, None, pain_points(lead, None))
    assert "163" in e["body"]
    assert "163" in e["subject"]

def test_email_never_claims_speed_improves_ranking():
    lead, audit = L(), A()
    body = cold_email(lead, audit, pain_points(lead, audit))["body"].lower()
    assert not ("rank" in body and "faster" in body)

def test_clean_site_gets_a_no_sell_email():
    lead = L(); audit = dict(performance=96, seo=95, accessibility=95, best_practices=95, lcp_ms=1100)
    e = cold_email(lead, audit, pain_points(lead, audit))
    assert e["pain_code"] is None
    assert "Nothing to sell" in e["body"]

def test_call_opener_leads_with_the_number():
    lead, audit = L(), A()
    assert "31/100" in call_opener(lead, audit, pain_points(lead, audit))

def test_call_opener_for_no_website_asks_a_question():
    lead = L(has_website=False, website=None)
    assert call_opener(lead, None, pain_points(lead, None)).rstrip().endswith("?")

def test_email_is_short():
    lead, audit = L(), A()
    assert len(cold_email(lead, audit, pain_points(lead, audit))["body"].split()) < 180

def test_candidate_emails_derived_from_domain():
    c = candidate_emails("https://www.bella.example/page")
    assert c[0] == "info@bella.example"
    assert all("@bella.example" in e for e in c)

def test_candidate_emails_rejects_garbage():
    assert candidate_emails("") == []
    assert candidate_emails("notadomain") == []
