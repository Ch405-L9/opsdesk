#!/usr/bin/env python3
"""icp - natural-language front end for the ICP intelligence tools.

Usage is conversational:
    icp find me med spas in Lawrenceville GA
    icp check billybutlerhvac.com
    icp what's my budget
    icp                      # interactive, type naturally, Ctrl-D to exit

Routing has two layers, deliberately:
  1. A deterministic regex router (icp.nl.route). Instant, offline, unambiguous.
  2. badgr-orchestrator via Ollama, for phrasings layer 1 does not know.
Layer 2 is only reached on a miss, so the common path never waits on inference
and never depends on Ollama being up.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
PROJECT = PKG_ROOT.parent
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(PKG_ROOT))

from icp.audit import PsiAudit
from icp.budget import BudgetExceeded, BudgetLedger, load_quotas
from icp.discovery import PlacesDiscovery
from icp.nl import route
from icp.providers import ProviderUnavailable, load_dotenv
from icp.scoring import score_lead
from icp.store import Store
from icp.enrich import enrich_one, export_csv, export_xlsx

CONFIG = PROJECT / "config" / "providers.json"
STATE = PROJECT / "state" / "api_usage.json"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
ORCHESTRATOR = "badgr-orchestrator"

C_OK, C_WARN, C_ERR, C_DIM, C_OFF = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    C_OK = C_WARN = C_ERR = C_DIM = C_OFF = ""

def _ledger() -> BudgetLedger:
    load_dotenv(PROJECT / ".env")
    quotas, posture = load_quotas(CONFIG)
    return BudgetLedger(STATE, quotas, posture)

# ── actions ───────────────────────────────────────────────────────────────────

def do_budget() -> int:
    led = _ledger()
    print(f"{C_DIM}spend posture: {int(led.spend_posture*100)}% of each free allowance"
          f"   month: {led.month}{C_OFF}")
    print(f"{'provider':11}{'limit':>8}{'usable':>8}{'spent':>7}{'left':>7}  key  unit")
    for name, r in sorted(led.report().items()):
        left = r["remaining"]
        colour = C_ERR if left == 0 else (C_WARN if left < r["usable"] * 0.25 else C_OK)
        key = f"{C_OK}yes{C_OFF}" if r["key_present"] else f"{C_ERR}NO {C_OFF}"
        print(f"{name:11}{r['limit']:>8}{r['usable']:>8}{r['spent']:>7}"
              f"{colour}{left:>7}{C_OFF}  {key}  {r['unit']}")
    return 0

def do_keys() -> int:
    script = PROJECT / "tools" / "validate_keys.py"
    if not script.exists():
        print(f"{C_ERR}validator missing: {script}{C_OFF}")
        return 1
    os.execv(sys.executable, [sys.executable, str(script)])

def do_find(industry: str, location: str | None, limit: int = 20, fresh: bool = False) -> int:
    if not location:
        print(f"{C_WARN}Where? e.g. 'find {industry} in Lawrenceville GA'{C_OFF}")
        return 2

    led = _ledger()
    store = Store()

    # Cache first. Places bills at the ENTERPRISE SKU ($35/1,000 after 1,000
    # free calls/month) because we request website/phone/rating/reviews. A
    # repeat search inside the TTL must never cost a call.
    rows = None if fresh else store.cached_search(industry, location)
    if rows is not None:
        age = store.cache_age_days(industry, location) or 0
        print(f"{C_DIM}cached result ({age:.1f} days old, cost 0) - say 'fresh' to force a refetch{C_OFF}")
    else:
        try:
            # Always request 20: price is per REQUEST, not per result.
            rows = PlacesDiscovery(led).search(industry, location, max_results=20)
        except ProviderUnavailable as e:
            print(f"{C_ERR}{e}{C_OFF}"); return 1
        except BudgetExceeded as e:
            print(f"{C_ERR}{e}{C_OFF}")
            print(f"{C_DIM}This is the guardrail working. Raise spend_posture in "
                  f"config/providers.json only if the dashboard agrees.{C_OFF}")
            return 1
        except Exception as e:
            print(f"{C_ERR}search failed: {type(e).__name__}: {str(e)[:160]}{C_OFF}"); return 1
        store.put_search(industry, location, rows)

    if not rows:
        print(f"{C_WARN}No results for '{industry}' in '{location}'.{C_OFF}")
        return 0

    vertical = (industry or "").strip().lower().replace(" ", "_")
    scored = []
    for r in rows:
        r = dict(r, vertical=vertical)
        scored.append({**r, **score_lead(r, None)})
    scored.sort(key=lambda x: -x["priority"])
    store.upsert_leads(scored, vertical=vertical, location=location)

    no_site = [r for r in scored if not r["has_website"]]
    dq = [r for r in scored if r["disqualified"]]
    print(f"\n{len(scored)} businesses  {C_DIM}(places {led.spent('places')}/"
          f"{led.usable('places')} used this month | {store.count_leads()} leads stored){C_OFF}")
    if no_site:
        print(f"{C_OK}{len(no_site)} with NO WEBSITE{C_OFF} "
              f"{C_DIM}- strongest need signal; a SERP can never surface these{C_OFF}")
    if dq:
        print(f"{C_DIM}{len(dq)} disqualified (franchise/directory/closed){C_OFF}")
    print()
    print(f"  {'business':34}{'pri':>4}{'need':>5}{'abil':>5}  phone          website")
    for r in scored:
        if r["disqualified"]:
            continue
        col = C_OK if r["priority"] >= 70 else (C_WARN if r["priority"] >= 50 else C_DIM)
        site = r["website"] or f"{C_OK}(NO WEBSITE){C_OFF}"
        print(f"  {r['name'][:32]:34}{col}{r['priority']:>4}{C_OFF}{r['need']:>5}{r['ability']:>5}"
              f"  {(r.get('phone') or '-'):15}{site[:46]}")
    print(f"\n{C_DIM}stored in ~/.local/share/badgr/icp.db - 'icp top leads' to see the best{C_OFF}")
    return 0


def do_top(limit: int = 15) -> int:
    store = Store()
    rows = store.top_leads(limit=limit)
    if not rows:
        print(f"{C_WARN}No leads stored yet. Try: icp find me med spas in Lawrenceville GA{C_OFF}")
        return 0
    print(f"\ntop {len(rows)} of {store.count_leads()} stored leads\n")
    print(f"  {'business':34}{'pri':>4}{'need':>5}{'abil':>5}  phone          vertical")
    for r in rows:
        col = C_OK if r["priority"] >= 70 else (C_WARN if r["priority"] >= 50 else C_DIM)
        print(f"  {(r['name'] or '')[:32]:34}{col}{r['priority']:>4}{C_OFF}"
              f"{r['need']:>5}{r['ability']:>5}  {(r['phone'] or '-'):15}{r['vertical'] or ''}")
    counts = store.outcome_counts()
    if counts:
        print(f"\n{C_DIM}outcomes logged: {counts}{C_OFF}")
    return 0


def do_audit(url: str) -> int:
    led = _ledger()
    print(f"{C_DIM}running Lighthouse on {url} (server-side, ~10-30s)...{C_OFF}")
    try:
        a = PsiAudit(led).audit(url)
    except (ProviderUnavailable, BudgetExceeded) as e:
        print(f"{C_ERR}{e}{C_OFF}"); return 1
    except Exception as e:
        print(f"{C_ERR}audit failed: {type(e).__name__}: {str(e)[:200]}{C_OFF}"); return 1

    def bar(score):
        if score is None: return f"{C_DIM}  n/a{C_OFF}"
        col = C_ERR if score < 50 else (C_WARN if score < 90 else C_OK)
        return f"{col}{score:>5}{C_OFF}"
    print(f"\n  {url}")
    for label, key in [("performance", "performance"), ("SEO", "seo"),
                       ("accessibility", "accessibility"), ("best practices", "best_practices")]:
        print(f"    {label:16}{bar(a[key])}")
    if a["lcp_ms"]:
        col = C_ERR if a["lcp_ms"] > 4000 else (C_WARN if a["lcp_ms"] > 2500 else C_OK)
        print(f"    {'LCP':16}{col}{a['lcp_ms']/1000:>5.1f}s{C_OFF}")
    if not a["has_field_data"]:
        print(f"    {C_DIM}no CrUX field data (normal for small local businesses){C_OFF}")
    return 0

def do_enrich(limit: int = 3, verify: bool = False) -> int:
    """Full CRM-grade workup on the top N leads. Default 3 - a day of calls."""
    led, store = _ledger(), Store()
    rows = store.top_leads(limit=limit)
    if not rows:
        print(f"{C_WARN}No leads stored. Try: icp find me med spas in Lawrenceville GA{C_OFF}")
        return 0

    print(f"{C_DIM}enriching top {len(rows)} leads - Lighthouse audit each "
          f"(server-side, ~10-30s per site){C_OFF}\n")
    records = []
    for i, r in enumerate(rows, 1):
        lead = dict(r)
        lead["has_website"] = bool(r["has_website"])
        print(f"  [{i}/{len(rows)}] {r['name'][:40]}...", end=" ", flush=True)
        rec = enrich_one(lead, led, verify_email=verify)
        records.append(rec)
        sc = rec["scores_worst_to_best"] or "no site"
        print(f"{C_OK}done{C_OFF}  {C_DIM}{sc[:52]}{C_OFF}")

    stamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M")
    csv_p = export_csv(records, PROJECT / f"leads_enriched_{stamp}.csv")
    xl_p = export_xlsx(records, PROJECT / f"leads_enriched_{stamp}.xlsx")

    print(f"\n{'='*74}")
    for rec in records:
        print(f"\n{C_OK}{rec['business_name']}{C_OFF}  "
              f"{C_DIM}tier {rec['tier']} | priority {rec['priority']} | {rec['vertical']}{C_OFF}")
        print(f"  phone   {rec['phone'] or '-'}")
        print(f"  email   {rec['email_best'] or '-'}  ({rec['email_status']})")
        print(f"  address {(rec['address'] or '-')[:60]}")
        print(f"  site    {rec['website'] or '(NONE)'}")
        if rec["scores_worst_to_best"]:
            print(f"  scores  {rec['scores_worst_to_best']}   {C_DIM}(worst first){C_OFF}")
        print(f"  {C_WARN}PAIN{C_OFF}    {rec['pain_1']}")
        print(f"          {C_DIM}{rec['pain_1_evidence'][:150]}{C_OFF}")
        print(f"  {C_OK}SELL{C_OFF}    {rec['pain_1_service']}  ->  {rec['pain_1_value']}")
        print(f"          {C_DIM}{rec['pain_1_angle'][:150]}{C_OFF}")
        if rec["pain_2"]:
            print(f"  also    {rec['pain_2']}" + (f" | {rec['pain_3']}" if rec["pain_3"] else ""))
        print(f"  {C_DIM}CALL:{C_OFF} {rec['call_opener'][:160]}")

    print(f"\n{'='*74}")
    print(f"{C_OK}CSV {C_OFF} {csv_p}")
    if xl_p:
        print(f"{C_OK}XLSX{C_OFF} {xl_p}")
    print(f"{C_DIM}places {led.spent('places')}/{led.usable('places')} | "
          f"psi {led.spent('psi')}/{led.usable('psi')} | "
          f"hunter {led.spent('hunter')}/{led.usable('hunter')}{C_OFF}")
    return 0


def do_outcome(event: str, target: str) -> int:
    """Record what actually happened. This is the only thing that can ever turn
    the scoring weights from reasoning into measured fact."""
    store = Store()
    rows = [r for r in store.top_leads(limit=500)
            if target.lower() in ((r["name"] or "") + " " + (r["website"] or "")).lower()]
    if not rows:
        print(f"{C_WARN}No stored lead matching '{target}'. Run a search first.{C_OFF}")
        return 2
    row = rows[0]
    store.log_outcome(row["domain_or_name"], event)
    counts = store.outcome_counts()
    print(f"{C_OK}logged{C_OFF} {event} -> {row['name']}")
    print(f"{C_DIM}outcomes so far: {counts}{C_OFF}")
    total = sum(counts.values())
    if total < 30:
        print(f"{C_DIM}{30-total} more outcomes until the scorer can be retrained "
              f"on your real results instead of market priors.{C_OFF}")
    return 0


def do_help() -> int:
    print(f"""
{C_OK}icp{C_OFF} - talk to it normally. Examples:

  {C_DIM}discovery{C_OFF}
    icp find me med spas in Lawrenceville GA
    icp look for dentists in Duluth GA
    icp show me roofers in Gwinnett County

  {C_DIM}auditing{C_OFF}
    icp check billybutlerhvac.com
    icp how fast is example.com

  {C_DIM}housekeeping{C_OFF}
    icp what's my budget
    icp are my keys good
    icp top leads              (best stored prospects, costs nothing)

  {C_DIM}shorthand{C_OFF}
    icp b          budget        icp t     top leads
    icp k          keys          icp h     help
    icp med spas in Lawrenceville GA     (no verb needed)

  {C_DIM}track what happened (makes the scorer learn){C_OFF}
    icp enrich                 full CRM workup on top 3 (audit + pain + email)
    icp enrich 5               same, top 5
    icp enrich verify          also verify the email with Hunter

  {C_DIM}track what happened (makes the scorer learn){C_OFF}
    icp called Omni Family Dental
    icp won Lavender Med Spa
    icp lost Kontour

  {C_DIM}interactive{C_OFF}
    icp                 (then just type; Ctrl-D to exit)

Anything it doesn't recognise goes to {ORCHESTRATOR} on Ollama.
""")
    return 0

# ── model fallback ────────────────────────────────────────────────────────────

SYSTEM = """You translate a request about local-business prospecting into ONE JSON object.
Reply with JSON only, no prose, no markdown fence.
Schema: {"intent": one of "find"|"audit"|"budget"|"keys"|"help",
         "industry": string or null, "location": string or null, "url": string or null}
Examples:
"get me some hvac companies around duluth" -> {"intent":"find","industry":"hvac","location":"Duluth GA","url":null}
"is acme.com any good" -> {"intent":"audit","industry":null,"location":null,"url":"https://acme.com"}
"how many credits do i have" -> {"intent":"budget","industry":null,"location":null,"url":null}"""

def ask_model(text: str) -> dict | None:
    try:
        import requests
        r = requests.post(OLLAMA_URL, timeout=60, json={
            "model": ORCHESTRATOR, "stream": False, "format": "json",
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": text}]})
        r.raise_for_status()
        return json.loads(r.json()["message"]["content"])
    except Exception as e:
        print(f"{C_DIM}(orchestrator unavailable: {type(e).__name__}){C_OFF}")
        return None

def handle(text: str) -> int:
    r = route(text)
    if r["intent"] == "unknown":
        print(f"{C_DIM}asking {ORCHESTRATOR}...{C_OFF}")
        m = ask_model(text)
        if not m or not m.get("intent"):
            print(f"{C_WARN}Didn't catch that. Try 'icp help'.{C_OFF}")
            return 2
        r = {"intent": m.get("intent"), "industry": m.get("industry"),
             "location": m.get("location"), "url": m.get("url")}

    i = r["intent"]
    if i == "budget": return do_budget()
    if i == "keys":   return do_keys()
    if i == "help":   return do_help()
    if i == "audit":  return do_audit(r["url"]) if r.get("url") else do_help()
    if i == "top":    return do_top()
    if i == "outcome": return do_outcome(r["event"], r["target"])
    if i == "enrich": return do_enrich(r.get("limit") or 3, r.get("verify", False))
    if i == "find":   return do_find(r.get("industry") or "", r.get("location"),
                                     fresh=r.get("fresh", False))
    print(f"{C_WARN}Unknown intent {i!r}.{C_OFF}")
    return 2

def main() -> int:
    args = sys.argv[1:]
    if args:
        return handle(" ".join(args))
    print(f"{C_OK}icp{C_OFF} - type naturally, Ctrl-D to exit. 'help' for examples.")
    while True:
        try:
            line = input(f"{C_OK}>{C_OFF} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); return 0
        if line.lower() in {"exit", "quit", "q"}: return 0
        if line:
            try: handle(line)
            except Exception as e: print(f"{C_ERR}{type(e).__name__}: {e}{C_OFF}")

if __name__ == "__main__":
    sys.exit(main())
