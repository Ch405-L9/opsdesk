"""Lead research: cache-first Places discovery, PageSpeed audits, scoring, outreach drafts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from opsdesk import timeutil
from opsdesk.leads.audit import PsiAudit
from opsdesk.leads.budget import BudgetLedger, ProviderQuota
from opsdesk.leads.discovery import PlacesDiscovery
from opsdesk.leads.model import demo_leads, parse_query
from opsdesk.leads.outreach import call_opener, cold_email
from opsdesk.leads.painpoints import pain_points
from opsdesk.leads.scoring import score_lead
from opsdesk.paths import AppPaths
from opsdesk.profile import BusinessProfile, load_profile
from opsdesk.secrets import load_secret
from opsdesk.workbench import add_source, get_item, log, upsert_item, workbench

CACHE_DAYS = 14
QUOTAS = {
    "places": ProviderQuota("places", 1000, "Text Search calls", "GOOGLE_PLACES_API_KEY",
                            "Google Places Text Search (Enterprise fields): 1,000 free calls/month"),
    "psi": ProviderQuota("psi", 20000, "audits", "PAGESPEED_API_KEY",
                         "PageSpeed Insights API: about 25,000/day free; local cap kept lower"),
}


def ledger(paths: AppPaths, posture: float = 0.8) -> BudgetLedger:
    return BudgetLedger(paths.data_dir / "quota_ledger.json", QUOTAS, spend_posture=posture)


def lead_key(row: dict[str, Any]) -> str:
    site = row.get("website") or ""
    host = urlsplit(site if "://" in site else f"https://{site}").hostname if site else None
    if host:
        return "lead:" + host.removeprefix("www.").lower()
    digits = re.sub(r"\D", "", str(row.get("phone") or ""))
    basis = f"{row.get('name', '')}|{digits}".lower()
    return "lead:n-" + hashlib.sha1(basis.encode()).hexdigest()[:16]


def _cache_key(industry: str, location: str) -> str:
    return f"{industry.strip().lower()}|{location.strip().lower()}"


@dataclass
class FindResult:
    rows: list[dict[str, Any]]
    source: str
    inserted: int = 0
    updated: int = 0
    spent_call: bool = False


def plan_find(paths: AppPaths, query: str) -> dict[str, Any]:
    """Dry run: what a search would cost, without touching the network."""
    profile = load_profile(paths.profile_file)
    default_loc = ", ".join(p for p in (profile.home_city, profile.home_state) if p)
    industry, location = parse_query(query, default_loc)
    with workbench(paths) as conn:
        row = conn.execute("SELECT fetched_at FROM search_cache WHERE query_key=?",
                           (_cache_key(industry, location),)).fetchone()
    cached_age = None
    if row:
        fetched = timeutil.parse_date(row["fetched_at"])
        cached_age = (timeutil.today() - fetched).days if fetched else None
    key = load_secret(paths, "google_places")
    led = ledger(paths)
    fresh = cached_age is not None and cached_age <= CACHE_DAYS
    return {
        "industry": industry, "location": location, "has_key": bool(key), "cached_days": cached_age,
        "cost_calls": 0 if (fresh or not key) else 1, "remaining": led.remaining("places"),
        "usable": led.usable("places"),
        "mode": "cache" if fresh else ("api" if key else "demo"),
    }


def find(paths: AppPaths, query: str, *, confirmed: bool = False, demo: bool = False,
         refresh: bool = False, limit: int = 20, session: Any = None) -> FindResult:
    plan = plan_find(paths, query)
    industry, location = plan["industry"], plan["location"]
    if not industry or not location:
        raise ValueError("Say what and where, e.g. 'dentists in Austin TX' (or set home city with `opsdesk init`).")
    rows: list[dict[str, Any]]
    spent = False
    with workbench(paths) as conn:
        cached = conn.execute("SELECT payload_json FROM search_cache WHERE query_key=?",
                              (_cache_key(industry, location),)).fetchone()
        if demo or (plan["mode"] == "demo" and not refresh):
            rows, source = demo_leads(industry, location), "demo (synthetic)"
        elif plan["mode"] == "cache" and not refresh and cached:
            rows, source = json.loads(cached["payload_json"]), f"cache ({plan['cached_days']} days old, free)"
        else:
            if not plan["has_key"]:
                raise RuntimeError("No Google Places key. Add one with `opsdesk keys set google_places`, or use --demo.")
            if not confirmed:
                raise PermissionError("This search spends 1 Google Places call. Re-run and confirm.")
            client = PlacesDiscovery(ledger(paths), api_key=load_secret(paths, "google_places"), session=session)
            rows = client.search(industry, location, max_results=limit)
            spent = True
            source = "Google Places API (1 call)"
            conn.execute(
                "INSERT OR REPLACE INTO search_cache(query_key,payload_json,fetched_at,provider) VALUES(?,?,?,?)",
                (_cache_key(industry, location), json.dumps(rows), timeutil.now_iso(), "google_places"),
            )
        src = add_source(conn, "leads", "api" if spent else "cache" if "cache" in source else "demo",
                         f"{industry} in {location}", "Google Places data: follow Google Maps Platform terms")
        result = FindResult(rows=[], source=source, spent_call=spent)
        for raw in rows[:limit]:
            lead = {**raw, "vertical": industry.lower().replace(" ", "_"), "location": location}
            lead.update(score_lead(lead, lead.get("audit")))
            lead["score"] = lead.pop("priority", 0)
            lead["key"] = lead_key(lead)
            outcome = upsert_item(conn, lead["key"], {k: v for k, v in lead.items() if k != "key"}, src)
            result.inserted += outcome == "inserted"
            result.updated += outcome == "updated"
            result.rows.append(lead)
        log(conn, "leads.find", None, {"query": query, "source": source, "count": len(result.rows)})
    result.rows.sort(key=lambda r: -(r.get("score") or 0))
    return result


def audit(paths: AppPaths, wb_key: str, *, confirmed: bool = False, session: Any = None) -> dict[str, Any]:
    with workbench(paths) as conn:
        item = get_item(conn, wb_key)
        if item is None:
            raise KeyError(f"No lead {wb_key!r}")
        if not item.get("website"):
            raise ValueError("This business has no website to audit. That is itself the pain point.")
        if not confirmed:
            raise PermissionError("An audit spends 1 PageSpeed call. Re-run and confirm.")
        result = PsiAudit(ledger(paths), api_key=load_secret(paths, "pagespeed"), session=session).audit(item["website"])
        payload = {k: v for k, v in item.items() if k not in
                   {"wb_key", "status", "priority", "done", "contacted", "followup_date", "followup_note", "notes", "updated_at"}}
        payload["audit"] = result
        payload.update(score_lead(payload, result))
        payload["score"] = payload.pop("priority", 0)
        payload["pains"] = pain_points(payload, result)
        upsert_item(conn, wb_key, payload)
        log(conn, "leads.audit", wb_key, {"performance": result.get("performance")})
        return payload


def sender(profile: BusinessProfile) -> dict[str, str]:
    return {"name": profile.owner_name or "Your Name", "company": profile.business_name or "Your Business",
            "area": profile.home_city or "your area"}


def draft(paths: AppPaths, wb_key: str) -> dict[str, str]:
    profile = load_profile(paths.profile_file)
    with workbench(paths) as conn:
        item = get_item(conn, wb_key)
        if item is None:
            raise KeyError(f"No lead {wb_key!r}")
        pains = item.get("pains") or pain_points(item, item.get("audit"))
        email = cold_email(item, item.get("audit"), pains, sender=sender(profile))
        opener = call_opener(item, item.get("audit"), pains, sender=sender(profile))
        log(conn, "leads.draft", wb_key, {"subject": email.get("subject")})
    return {"subject": email["subject"], "body": email["body"], "call_opener": opener}


def quota_report(paths: AppPaths) -> dict[str, Any]:
    led = ledger(paths)
    rep = led.report()
    for name in rep:
        rep[name]["key_present"] = bool(load_secret(paths, {"places": "google_places", "psi": "pagespeed"}[name]))
    return rep
