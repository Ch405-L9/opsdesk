"""Tests for the pure logic in root_scraper: URL building and result parsing.

No network access required - parsing runs against saved fixtures in tests/fixtures.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import root_scraper as rs

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def test_build_search_url_keeps_scheme_host_and_path():
    """The original bug: the query was concatenated straight onto the host."""
    url = rs.build_search_url(rs.SEARCH_ENGINES[0], "HVAC Repair", "Lawrenceville GA")
    assert url.startswith("https://"), url
    # the query must live in the query string, never glued to the hostname
    assert "duckduckgo.comhvac" not in url.lower()
    assert "?" in url
    host = url.split("://", 1)[1].split("/", 1)[0]
    assert "+" not in host and "%" not in host, f"query leaked into host: {host}"
    assert "hvac+repair+lawrenceville+ga" in url.lower()


def test_build_search_url_for_every_engine():
    for engine in rs.SEARCH_ENGINES:
        url = rs.build_search_url(engine, "Roofing", "Atlanta GA")
        host = url.split("://", 1)[1].split("/", 1)[0]
        assert "+" not in host and "%" not in host, f"{engine.name}: {url}"
        assert "roofing+atlanta+ga" in url.lower(), f"{engine.name}: {url}"


def test_extract_leads_from_brave_fixture():
    html = (FIXTURES / "brave_results.html").read_text(encoding="utf-8")
    engine = rs.engine_by_name("brave")
    leads = rs.extract_leads(html, engine)
    assert len(leads) >= 5, f"expected real business domains, got {leads}"
    domains = {lead["name"] for lead in leads}
    # known business results present in the fixture
    assert any("coolray" in d for d in domains), domains
    # engine chrome, social networks and directories must be filtered out
    assert not any("brave.com" in d for d in domains), domains
    assert not any("facebook.com" in d for d in domains), domains
    assert not any("reddit.com" in d for d in domains), domains


def test_extract_leads_from_startpage_fixture():
    html = (FIXTURES / "startpage_results.html").read_text(encoding="utf-8")
    engine = rs.engine_by_name("startpage")
    leads = rs.extract_leads(html, engine)
    assert len(leads) >= 5, f"expected real business domains, got {leads}"
    assert not any("startpage.com" in lead["name"] for lead in leads), leads
    assert not any("admarketplace" in lead["name"] for lead in leads), leads


def test_extract_leads_are_unique_and_well_formed():
    html = (FIXTURES / "brave_results.html").read_text(encoding="utf-8")
    leads = rs.extract_leads(html, rs.engine_by_name("brave"))
    names = [lead["name"] for lead in leads]
    assert len(names) == len(set(names)), f"duplicate domains: {names}"
    for lead in leads:
        assert lead["website"].startswith("http"), lead
        assert lead["name"] and "/" not in lead["name"], lead


def test_extract_leads_unwraps_duckduckgo_redirects():
    html = (
        '<html><body>'
        '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample-hvac.com%2F&amp;rut=abc">Example HVAC</a>'
        '</body></html>'
    )
    leads = rs.extract_leads(html, rs.engine_by_name("duckduckgo"))
    assert leads == [{"name": "example-hvac.com", "website": "https://example-hvac.com/"}], leads


def test_extract_leads_on_empty_page_returns_empty_list():
    assert rs.extract_leads("<html><body>no results</body></html>", rs.SEARCH_ENGINES[0]) == []


def test_classify_flags_missing_ssl_as_warm_prospect():
    audit = rs.classify_audit(final_url="http://nossl.example.com", server="nginx", body="")
    assert audit["has_ssl"] is False
    assert audit["is_warm_prospect"] is True


def test_classify_flags_wordpress_as_warm_prospect():
    audit = rs.classify_audit(
        final_url="https://wp.example.com", server="Apache/2.4", body="<link href='/wp-content/x.css'>"
    )
    assert audit["has_ssl"] is True
    assert audit["is_warm_prospect"] is True
    assert "wordpress" in audit["signals"] or "apache" in audit["signals"]


def test_classify_leaves_modern_site_cold():
    audit = rs.classify_audit(final_url="https://modern.example.com", server="cloudflare", body="<html></html>")
    assert audit["has_ssl"] is True
    assert audit["is_warm_prospect"] is False
