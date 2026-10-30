import argparse
import time
import urllib.parse
from dataclasses import dataclass
from typing import List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from loguru import logger
from playwright.sync_api import sync_playwright
from pydantic import BaseModel

class BrowserBusinessRecord(BaseModel):
    name: str
    website: str
    has_ssl: bool = False
    server_header: Optional[str] = "Unknown"
    is_warm_prospect: bool = False
    signals: str = ""

@dataclass(frozen=True)
class SearchEngine:
    """A search front-end we can drive with a headless browser."""
    name: str
    url_template: str   # must contain the {query} placeholder inside the query string
    host_fragments: tuple  # substrings identifying the engine's own links

# Ordered by how reliably each one serves a headless browser. DuckDuckGo's
# html/lite endpoints answer 403 to datacenter IPs, so it sits last as a fallback.
SEARCH_ENGINES = (
    SearchEngine(
        name="brave",
        url_template="https://search.brave.com/search?q={query}",
        host_fragments=("brave.com", "brave.app"),
    ),
    SearchEngine(
        name="startpage",
        url_template="https://www.startpage.com/sp/search?query={query}",
        host_fragments=("startpage.com", "admarketplace.net"),
    ),
    SearchEngine(
        name="mojeek",
        url_template="https://www.mojeek.com/search?q={query}",
        host_fragments=("mojeek.com", "altcha.org"),
    ),
    SearchEngine(
        name="duckduckgo",
        url_template="https://html.duckduckgo.com/html/?q={query}",
        host_fragments=("duckduckgo.com", "duck.ai", "spreadprivacy.com"),
    ),
)

# Portals, directories and social networks are not prospects - they are noise.
EXCLUDED_HOST_FRAGMENTS = (
    "google.", "googleusercontent.com", "gstatic.com", "bing.com", "microsoft.com",
    "msn.com", "yahoo.com", "apple.com", "wikipedia.org", "archive.org",
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "youtu.be", "tiktok.com", "pinterest.com", "reddit.com",
    "nextdoor.com", "yelp.com", "yellowpages.com", "bbb.org", "thumbtack.com",
    "angi.com", "angieslist.com", "homeadvisor.com", "porch.com", "houzz.com",
    "indeed.com", "ziprecruiter.com", "glassdoor.com", "mapquest.com",
    "tripadvisor.com", "manta.com", "chamberofcommerce.com", "expertise.com",
    "birdeye.com", "nicelocal.com", "hackerone.com", "wordpress.org",
)

# Cheap fingerprints for sites that are likely to need optimization work.
WARM_BODY_SIGNALS = {
    "wordpress": ("wp-content", "wp-includes", 'name="generator" content="wordpress'),
    "jquery-legacy": ("jquery/1.", "jquery-1."),
    "page-builder": ("elementor", "wpbakery", "et_pb_"),
    "wix-or-weebly": ("wix.com", "weebly.com", "static.parastorage.com"),
}
WARM_SERVER_SIGNALS = ("apache", "litespeed", "iis")

def engine_by_name(name: str) -> SearchEngine:
    """Look up a configured engine, raising a clear error for an unknown name."""
    for engine in SEARCH_ENGINES:
        if engine.name == name:
            return engine
    known = ", ".join(e.name for e in SEARCH_ENGINES)
    raise ValueError(f"Unknown search engine '{name}'. Available: {known}")

def build_search_url(engine: SearchEngine, industry: str, location: str) -> str:
    """Build the search URL by substituting an encoded query into the template.

    The query is only ever placed in the template's {query} slot, which keeps it
    inside the query string instead of being concatenated onto the hostname.
    """
    search_query = " ".join(part for part in (industry, location) if part).strip()
    encoded_query = urllib.parse.quote_plus(search_query)
    return engine.url_template.format(query=encoded_query)

def _unwrap_redirect(href: str) -> Optional[str]:
    """Resolve an engine's click-tracking wrapper down to the real destination."""
    if href.startswith("//"):
        href = "https:" + href

    parsed = urllib.parse.urlparse(href)
    query_params = urllib.parse.parse_qs(parsed.query)

    # DuckDuckGo wraps results as /l/?uddg=<encoded>; Startpage and Brave use
    # their own redirect keys. Any of them carries the target as a parameter.
    for key in ("uddg", "url", "u", "q", "target"):
        candidates = query_params.get(key, [])
        if candidates and candidates[0].startswith("http"):
            return candidates[0]

    return href if href.startswith("http") else None

def _is_prospect_host(host: str, engine: SearchEngine) -> bool:
    if not host or "." not in host:
        return False
    if any(fragment in host for fragment in engine.host_fragments):
        return False
    return not any(fragment in host for fragment in EXCLUDED_HOST_FRAGMENTS)

def extract_leads(html: str, engine: SearchEngine) -> List[dict]:
    """Pull unique business domains out of a rendered results page.

    Result markup changes often and differs per engine, so rather than depending
    on one brittle CSS class we walk every anchor and keep the external hosts.
    """
    soup = BeautifulSoup(html, "html.parser")
    leads: List[dict] = []
    seen_hosts = set()

    for anchor in soup.find_all("a", href=True):
        actual_url = _unwrap_redirect(anchor["href"].strip())
        if not actual_url:
            continue

        host = urllib.parse.urlparse(actual_url).netloc.lower()
        host = host.split(":")[0]  # drop any port
        if not _is_prospect_host(host, engine):
            continue

        dedupe_key = host.removeprefix("www.")
        if dedupe_key in seen_hosts:
            continue

        seen_hosts.add(dedupe_key)
        leads.append({"name": host, "website": actual_url})

    return leads

class PlaywrightDiscovery:
    """Uses automated browser emulation to harvest business domains safely for zero cost."""

    def __init__(self, engines=SEARCH_ENGINES, min_results: int = 3, headless: bool = True):
        self.engines = tuple(engines)
        self.min_results = min_results
        self.headless = headless

    def discover(self, industry: str, location: str) -> List[dict]:
        """Try each engine in turn and return the first usable batch of leads."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            try:
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
                    ),
                    locale="en-US",
                    viewport={"width": 1366, "height": 900},
                )

                best: List[dict] = []
                for engine in self.engines:
                    target_url = build_search_url(engine, industry, location)
                    logger.info(f"Querying {engine.name}: {target_url}")

                    html = self._fetch_html(context, target_url)
                    if html is None:
                        continue

                    leads = extract_leads(html, engine)
                    logger.info(f"{engine.name} yielded {len(leads)} candidate domains.")

                    if len(leads) > len(best):
                        best = leads
                    if len(best) >= self.min_results:
                        return best

                return best
            finally:
                browser.close()

    @staticmethod
    def _fetch_html(context, target_url: str) -> Optional[str]:
        """Load a page and return its HTML, or None if it never settled.

        page.content() is retried because it raises while a page is still
        navigating, which is exactly the state a failed goto() leaves behind.
        """
        page = context.new_page()
        try:
            try:
                response = page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                if response is not None and response.status >= 400:
                    logger.warning(f"{target_url} answered HTTP {response.status}; skipping.")
                    return None
                page.wait_for_timeout(3000)  # let client-side result rendering finish
            except Exception as e:
                logger.warning(f"Navigation did not settle for {target_url}: {e}")

            for attempt in range(3):
                try:
                    return page.content()
                except Exception as e:
                    logger.debug(f"Content snapshot attempt {attempt + 1} failed: {e}")
                    page.wait_for_timeout(1500)

            logger.warning(f"Could not snapshot content for {target_url}.")
            return None
        finally:
            page.close()

def classify_audit(final_url: str, server: str, body: str) -> dict:
    """Score one site from its final URL, Server header and HTML body."""
    has_ssl = final_url.startswith("https://")
    signals = []

    if not has_ssl:
        signals.append("no-ssl")

    server_lower = (server or "").lower()
    for marker in WARM_SERVER_SIGNALS:
        if marker in server_lower:
            signals.append(marker)

    body_lower = (body or "").lower()
    for label, markers in WARM_BODY_SIGNALS.items():
        if any(marker in body_lower for marker in markers):
            signals.append(label)

    return {
        "has_ssl": has_ssl,
        "server_header": server or "Hidden",
        "is_warm_prospect": bool(signals),
        "signals": ",".join(signals),
    }

class LocalAuditor:
    """Profiles target web optimization vulnerabilities using raw meta parameters."""

    @staticmethod
    def audit_site(url: str) -> dict:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
            )
        }

        try:
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            return classify_audit(
                final_url=response.url,
                server=response.headers.get("Server", ""),
                body=response.text[:200_000],  # header + hero markup is enough to fingerprint
            )
        except Exception as e:
            logger.debug(f"Audit handshake skipped for {url}: {e}")
            return {
                "has_ssl": url.startswith("https://"),
                "server_header": "Unreachable",
                "is_warm_prospect": False,
                "signals": "unreachable",
            }

def run_root_pipeline(industry: str, city_state: str, output: str = "root_qualified_leads.csv",
                      delay: float = 1.0) -> List[dict]:
    discovery = PlaywrightDiscovery()
    raw_leads = discovery.discover(industry, city_state)

    if not raw_leads:
        logger.error(
            "Zero targets parsed. Every search front-end refused or returned no results - "
            "check connectivity, or retry later if this IP is being throttled."
        )
        return []

    logger.info(f"Discovered {len(raw_leads)} potential web endpoints. Executing audits...")
    processed_records = []

    for lead in raw_leads:
        metrics = LocalAuditor.audit_site(lead["website"])

        record = BrowserBusinessRecord(
            name=lead["name"],
            website=lead["website"],
            has_ssl=metrics["has_ssl"],
            server_header=metrics["server_header"],
            is_warm_prospect=metrics["is_warm_prospect"],
            signals=metrics["signals"],
        )
        processed_records.append(record.model_dump())
        logger.info(
            f"Target: {lead['website']} | Warm Prospect: {metrics['is_warm_prospect']}"
            f"{' (' + metrics['signals'] + ')' if metrics['signals'] else ''}"
        )
        time.sleep(delay)  # Graceful pause to pace network requests

    df = pd.DataFrame(processed_records)
    df.to_csv(output, index=False)
    warm = int(df["is_warm_prospect"].sum())
    logger.success(f"Pipeline finished: {warm}/{len(df)} warm prospects written to {output}")
    return processed_records

def main():
    parser = argparse.ArgumentParser(description="Discover and audit local business websites.")
    parser.add_argument("--industry", default="HVAC Repair")
    parser.add_argument("--location", default="Lawrenceville GA")
    parser.add_argument("--output", default="root_qualified_leads.csv")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds to wait between audits")
    args = parser.parse_args()

    run_root_pipeline(args.industry, args.location, output=args.output, delay=args.delay)

if __name__ == "__main__":
    main()
