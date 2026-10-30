#!/usr/bin/env python3
"""Free, unmetered lead discovery via DuckDuckGo HTML + local auditing.

FIXED 2026-10-27. The original was closer to working than it appeared - it
already used POST, which is the one transport DuckDuckGo still serves. Three
real bugs stopped it:

  1. It POSTed to https://duckduckgo.com (the site root) instead of
     https://html.duckduckgo.com/html/ - the root does not return results.
  2. It looked for the redirect key "/l/?kh=". The actual key is "uddg", so
     every wrapped result URL was discarded.
  3. Protocol-relative hrefs ("//duckduckgo.com/l/?...") failed the
     startswith("http") test and were dropped.

Note GET does NOT work - it returns an HTTP 202 anti-bot challenge. Only POST
returns results, which is also why driving a headless browser at it failed.

This costs nothing, so it is the right first try before spending a metered
credit. It is HTML scraping though, so it is best-effort: if DuckDuckGo changes
its markup this returns [] and you should fall back to:

    icp find me hvac companies in Lawrenceville GA     # Google Places (metered)
    python3 src/root_scraper.py                        # Brave/Startpage chain
"""
import sys
import time
from pathlib import Path
from typing import List, Optional

import pandas as pd
import requests
from loguru import logger
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
from icp.ddg import search as ddg_search


class FreeBusinessRecord(BaseModel):
    name: str
    website: str
    has_ssl: bool = False
    server_header: Optional[str] = "Unknown"
    is_warm_prospect: bool = False


class FreeAuditor:
    """Audits sites locally without third-party APIs by examining network metadata.

    Kept deliberately crude: this is the zero-cost path. For a real, defensible
    score use the PageSpeed Insights audit instead (`icp check <domain>`), which
    returns measured Lighthouse data rather than header guesses.
    """

    @staticmethod
    def audit_site(url: str) -> dict:
        audit = {"has_ssl": False, "server_header": "Unknown", "is_warm_prospect": False}
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
        try:
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            audit["has_ssl"] = response.url.startswith("https://")
            audit["server_header"] = response.headers.get("Server", "Hidden")
            if not audit["has_ssl"]:
                audit["is_warm_prospect"] = True
            if "wp-content" in response.text[:200_000].lower():
                audit["is_warm_prospect"] = True
        except Exception as e:
            logger.debug(f"Audit skipped for {url}: {e}")
        return audit


def run_free_pipeline(industry: str, city_state: str,
                      output: str = "free_qualified_leads.csv", delay: float = 1.0):
    logger.info(f"Free discovery: DuckDuckGo HTML for '{industry} {city_state}'...")
    raw_leads = ddg_search(industry, city_state)

    if not raw_leads:
        logger.error(
            "DuckDuckGo returned nothing - most likely its anti-bot challenge fired "
            "(HTTP 202). This path is best-effort and unmetered; fall back to "
            "'icp find me <industry> in <city>' which uses Google Places."
        )
        return []

    logger.info(f"Found {len(raw_leads)} endpoints. Auditing...")
    records = []
    for lead in raw_leads:
        metrics = FreeAuditor.audit_site(lead["website"])
        records.append(FreeBusinessRecord(
            name=lead["name"], website=lead["website"],
            has_ssl=metrics["has_ssl"], server_header=metrics["server_header"],
            is_warm_prospect=metrics["is_warm_prospect"],
        ).model_dump())
        logger.info(f"{lead['name']} | ssl={metrics['has_ssl']} | warm={metrics['is_warm_prospect']}")
        time.sleep(delay)

    df = pd.DataFrame(records)
    df.to_csv(output, index=False)
    logger.success(f"Saved {len(df)} leads to {output}")
    return records


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Free DuckDuckGo lead discovery.")
    ap.add_argument("--industry", default="HVAC Repair")
    ap.add_argument("--location", default="Lawrenceville GA")
    ap.add_argument("--output", default="free_qualified_leads.csv")
    ap.add_argument("--delay", type=float, default=1.0)
    a = ap.parse_args()
    run_free_pipeline(a.industry, a.location, a.output, a.delay)
