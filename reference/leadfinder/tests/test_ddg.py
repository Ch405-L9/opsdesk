import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from icp.ddg import parse_results, search, _unwrap

FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "ddg_post_results.html"

def test_parses_real_fixture_into_business_domains():
    leads = parse_results(FIX.read_text(encoding="utf-8"))
    assert len(leads) >= 4, leads
    hosts = {l["name"] for l in leads}
    assert any("coolmastershvac" in h for h in hosts), hosts

def test_aggregators_are_excluded():
    leads = parse_results(FIX.read_text(encoding="utf-8"))
    hosts = " ".join(l["name"] for l in leads)
    for bad in ("yelp.com", "duckduckgo.com", "facebook.com", "angi.com"):
        assert bad not in hosts, bad

def test_unwrap_uses_uddg_not_kh():
    """The original code keyed on '/l/?kh=' and dropped every result."""
    assert _unwrap("//duckduckgo.com/l/?uddg=https%3A%2F%2Facme.com%2F&rut=x") == "https://acme.com/"

def test_unwrap_rejects_non_http():
    assert _unwrap("/settings") is None
    assert _unwrap("javascript:void(0)") is None

def test_results_are_unique():
    leads = parse_results(FIX.read_text(encoding="utf-8"))
    names = [l["name"] for l in leads]
    assert len(names) == len(set(names))

class _Resp:
    status_code = 202
    text = "challenge"
class _Sess:
    def post(self, *a, **kw): return _Resp()

def test_bot_challenge_returns_empty_not_garbage():
    assert search("hvac", "atlanta", session=_Sess()) == []

def test_network_failure_returns_empty():
    class Boom:
        def post(self, *a, **kw): raise RuntimeError("down")
    assert search("hvac", "atlanta", session=Boom()) == []
