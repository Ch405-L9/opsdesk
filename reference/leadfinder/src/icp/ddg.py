"""DuckDuckGo HTML search - free, unmetered, no API key.

IMPORTANT, and the reason this was wrongly written off twice:

    GET  https://html.duckduckgo.com/html/?q=...   -> HTTP 202 bot challenge
    POST https://html.duckduckgo.com/html/  data={"q": ...}  -> HTTP 200 results

The GET form is intercepted by DuckDuckGo's anti-bot challenge. The POST form
is not. Playwright navigation is a GET, which is why driving a browser at it
also failed. The original free_scraper.py used POST and was closer to working
than it looked - its real bug was POSTing to the site root instead of /html/.

There is still no DuckDuckGo *API*: api.duckduckgo.com is Instant Answer only
and returns zero web results for a local-business query. This is HTML scraping,
so treat it as best-effort - it can break whenever the markup changes, and it
must never be the only discovery path. It costs nothing, so it is the right
first try before spending a metered credit.
"""
from __future__ import annotations

import urllib.parse
from typing import List

import requests
from bs4 import BeautifulSoup

ENDPOINT = "https://html.duckduckgo.com/html/"
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

# Aggregators and social networks are not prospects.
EXCLUDED = ("duckduckgo.com", "yelp.com", "angi.com", "thumbtack", "homeadvisor",
            "yellowpages", "bbb.org", "facebook.com", "instagram.com", "linkedin.com",
            "twitter.com", "x.com", "youtube.com", "reddit.com", "nextdoor.com",
            "mapquest", "houzz.com", "porch.com", "indeed.com", "wikipedia.org",
            "google.", "bing.com", "apple.com", "tripadvisor", "birdeye", "manta.com")

def _unwrap(href: str) -> str | None:
    """Resolve DuckDuckGo's /l/?uddg= redirect wrapper to the real destination."""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    if "/l/" in parsed.path:
        # The redirect key is 'uddg'. The original code looked for '/l/?kh=',
        # which is a different parameter, so every result was dropped.
        target = urllib.parse.parse_qs(parsed.query).get("uddg", [None])[0]
        return target if target and target.startswith("http") else None
    return href if href.startswith("http") else None

def parse_results(html: str) -> List[dict]:
    """Extract unique business domains from a DuckDuckGo HTML results page."""
    soup = BeautifulSoup(html, "html.parser")
    leads, seen = [], set()

    for anchor in soup.find_all("a", href=True):
        url = _unwrap(anchor["href"].strip())
        if not url:
            continue
        host = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
        if not host or "." not in host:
            continue
        if any(bad in host for bad in EXCLUDED):
            continue
        key = host.removeprefix("www.")
        if key in seen:
            continue
        seen.add(key)
        leads.append({"name": host, "website": url, "has_website": True, "source": "duckduckgo"})
    return leads

def search(industry: str, location: str, session=None, timeout: int = 25) -> List[dict]:
    """Free, unmetered discovery. Returns [] rather than raising on failure."""
    session = session or requests.Session()
    query = " ".join(p for p in (industry, location) if p).strip()
    try:
        response = session.post(ENDPOINT, data={"q": query},
                                headers={"User-Agent": USER_AGENT}, timeout=timeout)
        if response.status_code != 200:
            # 202 means the anti-bot challenge fired; nothing useful in the body.
            return []
        return parse_results(response.text)
    except Exception:
        return []
