import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from icp.enrich import FIELDS, enrich_one, export_csv, export_xlsx

class _Led:
    quotas = {}
def L(**kw):
    b = dict(name="Bella Med Spa", website=None, has_website=False, vertical="med_spa",
             review_count=163, rating=4.7, phone="(470) 292-3250", address="1 A St",
             priority=90, need=100, ability=80, fit=100, reach=85); b.update(kw); return b

def test_enrich_no_website_lead_needs_no_providers():
    r = enrich_one(L(), _Led(), do_audit=False)
    assert r["business_name"] == "Bella Med Spa"
    assert r["pain_1"] == "No website at all"
    assert "163" in r["email_body"]
    assert r["call_opener"].rstrip().endswith("?")
    assert r["tier"] == "A"

def test_every_declared_field_is_populated_or_blank_not_missing():
    r = enrich_one(L(), _Led(), do_audit=False)
    for f in FIELDS:
        assert f in r, f

def test_csv_roundtrip(tmp_path):
    recs = [enrich_one(L(), _Led(), do_audit=False)]
    p = export_csv(recs, tmp_path / "x.csv")
    text = p.read_text(encoding="utf-8")
    assert "Bella Med Spa" in text
    assert text.splitlines()[0].startswith("priority,tier,business_name")

def test_xlsx_written(tmp_path):
    recs = [enrich_one(L(), _Led(), do_audit=False)]
    p = export_xlsx(recs, tmp_path / "x.xlsx")
    assert p is not None and p.exists() and p.stat().st_size > 2000

def test_audit_failure_does_not_raise(tmp_path):
    class Boom:
        quotas = {}
    r = enrich_one(L(website="https://x.com", has_website=True), Boom(), do_audit=True)
    assert r["business_name"] == "Bella Med Spa"   # survived the provider blowing up
