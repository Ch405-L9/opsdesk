import pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from icp.store import Store

def S(tmp_path): return Store(tmp_path / "t.db")

def test_cache_miss_then_hit(tmp_path):
    s = S(tmp_path)
    assert s.cached_search("med spa", "Lawrenceville GA") is None
    s.put_search("med spa", "Lawrenceville GA", [{"name": "A"}])
    assert s.cached_search("med spa", "Lawrenceville GA") == [{"name": "A"}]

def test_cache_key_is_case_and_space_insensitive(tmp_path):
    s = S(tmp_path)
    s.put_search("Med Spa", " Lawrenceville GA ", [{"name": "A"}])
    assert s.cached_search("med spa", "lawrenceville ga") is not None

def test_expired_cache_returns_none(tmp_path):
    s = S(tmp_path)
    s.put_search("x", "y", [{"n": 1}])
    assert s.cached_search("x", "y", ttl=0) is None   # forces a paid refresh

def test_upsert_and_rank_leads(tmp_path):
    s = S(tmp_path)
    s.upsert_leads([
        {"name": "Low", "website": "https://low.com", "priority": 20, "has_website": True},
        {"name": "High", "website": "https://high.com", "priority": 90, "has_website": True},
    ], vertical="med_spa")
    top = s.top_leads()
    assert top[0]["name"] == "High"
    assert s.count_leads() == 2

def test_upsert_is_idempotent(tmp_path):
    s = S(tmp_path)
    row = [{"name": "A", "website": "https://a.com", "priority": 50, "has_website": True}]
    s.upsert_leads(row); s.upsert_leads(row)
    assert s.count_leads() == 1

def test_disqualified_leads_excluded_from_top(tmp_path):
    s = S(tmp_path)
    s.upsert_leads([{"name": "F", "website": "https://f.com", "priority": 0,
                     "disqualified": "FRANCHISE_URL_PATTERN", "has_website": True}])
    assert s.top_leads() == []

def test_outcome_logging(tmp_path):
    s = S(tmp_path)
    s.log_outcome("https://a.com", "contacted")
    s.log_outcome("https://a.com", "replied")
    assert s.outcome_counts() == {"contacted": 1, "replied": 1}
