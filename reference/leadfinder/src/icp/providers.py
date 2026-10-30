"""Thin clients for the metered APIs, each one gated by the budget ledger.

Every client follows the same contract:
  * no API key  -> `available` is False and calls raise ProviderUnavailable
                   without touching the network
  * no budget   -> calls raise BudgetExceeded before the request is sent
  * a sent call -> billed immediately, whether or not it succeeds

The last rule is deliberate. A request that reaches the provider and then 502s
has usually already been counted on their side, so counting it optimistically
is how the ledger drifts under the real usage.
"""
from __future__ import annotations

import os
from typing import List, Optional

import requests

from .budget import BudgetLedger

class ProviderUnavailable(RuntimeError):
    """Raised when a provider has no configured API key."""

class MeteredClient:
    """Shared key/budget gating for a metered provider."""

    provider: str = ""
    cost_per_call: int = 1

    def __init__(self, ledger: BudgetLedger, api_key: Optional[str] = None, session=None):
        quota = ledger.quotas[self.provider]
        self.ledger = ledger
        self.api_key = api_key if api_key is not None else os.environ.get(quota.env_key)
        self.session = session or requests.Session()

    @property
    def available(self) -> bool:
        return bool(self.api_key) and self.ledger.can_spend(self.provider, self.cost_per_call)

    def _authorize(self) -> None:
        """Check key, then budget, before anything leaves the machine."""
        if not self.api_key:
            quota = self.ledger.quotas[self.provider]
            raise ProviderUnavailable(
                f"{self.provider}: no API key. Set {quota.env_key} in your environment or .env"
            )
        # Raises BudgetExceeded if this call would cross the cap. Billing up front
        # means an exception mid-request cannot leave the call unaccounted for.
        self.ledger.spend(self.provider, self.cost_per_call)

class BraveSearch(MeteredClient):
    """Brave Search API - cheapest per call, so this is the workhorse for discovery."""

    provider = "brave"
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def search(self, query: str, count: int = 20, country: str = "us") -> List[dict]:
        self._authorize()
        response = self.session.get(
            self.endpoint,
            headers={
                "Accept": "application/json",
                # Key travels in a header so it never lands in logs or a URL.
                "X-Subscription-Token": self.api_key,
            },
            params={"q": query, "count": count, "country": country},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "description": r.get("description", "")}
            for r in payload.get("web", {}).get("results", [])
            if r.get("url")
        ]

class SerpApiSearch(MeteredClient):
    """SerpApi - real Google SERP data. Scarcer than Brave, so reserve it for
    ranking checks on prospects that already look qualified."""

    provider = "serpapi"
    endpoint = "https://serpapi.com/search"

    def search(self, query: str, location: str = "Georgia, United States") -> List[dict]:
        self._authorize()
        response = self.session.get(
            self.endpoint,
            params={
                "q": query,
                "location": location,
                "engine": "google",
                "api_key": self.api_key,  # SerpApi only accepts the key as a param
                "num": 20,
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            {"title": r.get("title", ""), "url": r.get("link", ""),
             "snippet": r.get("snippet", ""), "position": r.get("position")}
            for r in payload.get("organic_results", [])
            if r.get("link")
        ]

class HunterEmails(MeteredClient):
    """Hunter.io - the scarcest resource in the stack (~50 credits/month).

    Only ever call this for a prospect that has already cleared the ICP gate;
    at this allowance every lookup is roughly a day and a half of budget.
    """

    provider = "hunter"
    endpoint = "https://api.hunter.io/v2/domain-search"

    def domain_search(self, domain: str, limit: int = 5) -> List[dict]:
        self._authorize()
        response = self.session.get(
            self.endpoint,
            params={"domain": domain, "api_key": self.api_key, "limit": limit},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        emails = payload.get("data", {}).get("emails", []) or []
        return [
            {
                "email": e.get("value"),
                "confidence": e.get("confidence"),
                "first_name": e.get("first_name"),
                "last_name": e.get("last_name"),
                "position": e.get("position"),
            }
            for e in emails
            if e.get("value")
        ]

class HunterVerify(MeteredClient):
    """Hunter email VERIFIER - the tool's actual job.

    Hunter is not a business-discovery tool. It indexes corporate domains with
    predictable name patterns; a local business runs everything through one
    shared inbox, so domain-search returns little or nothing. Verified live:
    two 1,000-review med spas returned zero and one generic address.

    Verification is what it is for, and the account reflects that - 100
    verifications/month against 50 searches. Use it on a candidate address
    BEFORE sending, so a cold email does not bounce.
    """

    provider = "hunter"
    endpoint = "https://api.hunter.io/v2/email-verifier"

    def verify(self, email: str) -> dict:
        self._authorize()
        response = self.session.get(
            self.endpoint, params={"email": email, "api_key": self.api_key}, timeout=20)
        response.raise_for_status()
        d = response.json().get("data", {}) or {}
        return {
            "email": email,
            "status": d.get("status"),            # deliverable | undeliverable | risky | unknown
            "score": d.get("score"),
            "accept_all": d.get("accept_all"),
            "smtp_check": d.get("smtp_check"),
            "sendable": d.get("status") in ("deliverable", "risky"),
        }


def candidate_emails(domain: str) -> list:
    """Likely shared-inbox addresses for a local business, best first.

    Derived, not looked up - costs nothing. Verify one before sending rather
    than guessing at send time.
    """
    domain = (domain or "").lower().strip()
    domain = domain.split("//")[-1].split("/")[0].removeprefix("www.")
    if not domain or "." not in domain:
        return []
    return [f"{p}@{domain}" for p in
            ("info", "contact", "hello", "office", "frontdesk", "admin", "appointments")]


def load_dotenv(path=".env") -> int:
    """Load KEY=VALUE pairs from a .env file without adding a dependency.

    Existing environment variables win, so an explicit export always overrides
    the file. Returns how many new names were set.
    """
    from pathlib import Path

    env_file = Path(path)
    if not env_file.exists():
        return 0

    loaded = 0
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded
