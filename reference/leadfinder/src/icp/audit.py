"""Site auditing via the Google PageSpeed Insights API.

This replaces the Server-header guessing in the original root_scraper.py. That
approach measured CDN choice, not site quality: a site behind Cloudflare hides
its Server header and scored "healthy" regardless of how bad it actually was.
PSI returns a real Lighthouse audit, which is both accurate and defensible to
show a prospect.
"""
from __future__ import annotations

from typing import Optional

from .providers import MeteredClient

ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

def _score(categories: dict, name: str) -> Optional[int]:
    cat = categories.get(name) or {}
    raw = cat.get("score")
    return None if raw is None else round(raw * 100)

def parse_psi(payload: dict) -> dict:
    """Extract the scores we act on from a PSI response."""
    lh = payload.get("lighthouseResult", {}) or {}
    categories = lh.get("categories", {}) or {}
    audits = lh.get("audits", {}) or {}

    lcp = (audits.get("largest-contentful-paint") or {}).get("numericValue")
    # CrUX field data is absent for most small local businesses - too little
    # traffic. Lab scores are what we actually grade on.
    field = (payload.get("loadingExperience") or {}).get("metrics") or {}

    return {
        # The URL PSI actually ended on after redirects. This is the ONLY
        # trustworthy source for "is this site secure" - Google Places stores
        # whatever the owner typed into their profile, usually the stale
        # http:// form even when the site redirects to HTTPS. Verified: 9 of 10
        # stored http:// leads served working HTTPS.
        "final_url": lh.get("finalUrl") or payload.get("id") or None,
        "performance": _score(categories, "performance"),
        "seo": _score(categories, "seo"),
        "accessibility": _score(categories, "accessibility"),
        "best_practices": _score(categories, "best-practices"),
        "lcp_ms": None if lcp is None else round(lcp),
        "has_field_data": bool(field),
    }

class PsiAudit(MeteredClient):
    provider = "psi"

    def audit(self, url: str, strategy: str = "mobile") -> dict:
        self._authorize()
        response = self.session.get(
            ENDPOINT,
            params={"url": url, "key": self.api_key, "strategy": strategy,
                    "category": ["performance", "seo", "accessibility", "best-practices"]},
            timeout=120,   # Lighthouse runs server-side and is genuinely slow
        )
        response.raise_for_status()
        return parse_psi(response.json())
