"""Bid finder, offline half: rank cached USAspending awards into reachable lanes.

No network here. Input is the cache written by `python3 -m badgr_funding.bidfetch`.
Scores are prioritization only ("fit"), never odds of winning. Set-asides that need a
certification the business does not hold are listed as blocked, not ranked.
"""
import json
import statistics
from collections import defaultdict
from pathlib import Path

from badgr_funding import dates

NAICS = ("541511", "541519")
STATE = "GA"
# Small-business set-aside codes open to a self-certified small business.
SB_SET_ASIDE = ("SBA", "SBP", "RSB", "ESB")
# Codes that need an SBA/VA certification the business does not hold (SBS shows none).
CERT_SET_ASIDE = ("8A", "8AN", "HZC", "HZS", "SDVOSBC", "SDVOSBS", "WOSB", "WOSBSS", "EDWOSB", "EDWOSBSS", "VSA", "VSS")
SAT = 350_000          # simplified acquisition threshold
MICRO = 15_000         # micro-purchase range (agency card buys; rarely posted)
CACHE_DIR = Path("data/bids")


def normalize(raw, tag):
    """One USAspending search row -> a flat award dict. tag: sb_set_aside | cert_required | any."""
    naics = raw.get("NAICS") or {}
    return {
        "id": raw.get("generated_internal_id") or raw.get("Award ID"),
        "award_id": raw.get("Award ID"),
        "recipient": (raw.get("Recipient Name") or "").strip(),
        "amount": float(raw.get("Award Amount") or 0),
        "agency": raw.get("Awarding Agency") or "",
        "sub_agency": raw.get("Awarding Sub Agency") or "",
        "start": raw.get("Start Date"),
        "end": raw.get("End Date"),
        "naics": naics.get("code") if isinstance(naics, dict) else naics,
        "tag": tag,
    }


def merge(batches):
    """batches: [(tag, rows)]. Dedupe by id; the most specific tag wins (cert > sb > any)."""
    rank = {"cert_required": 2, "sb_set_aside": 1, "any": 0}
    out = {}
    for tag, rows in batches:
        for raw in rows:
            a = normalize(raw, tag)
            if not a["id"]:
                continue
            prev = out.get(a["id"])
            if prev is None or rank[tag] > rank[prev["tag"]]:
                out[a["id"]] = a
    return list(out.values())


def lane(a):
    if a["tag"] == "cert_required":
        return "blocked"
    if a["amount"] > 2_000_000:
        return "subcontract"
    if a["tag"] == "sb_set_aside":
        return "sb_set_aside"
    return "full_and_open"


def competition_level(a):
    """Rough field size from the set-aside status; unknown when the record says nothing."""
    return {"sb_set_aside": "lower", "full_and_open": "higher", "subcontract": "n/a (prime)", "blocked": "n/a"}[lane(a)]


def fit(a, buyer_counts, today=None):
    """Return (score 0-100, reasons). Prioritization only."""
    today = today or dates.today()
    reasons, score = [], 0
    ln = lane(a)
    if ln == "blocked":
        return 0, ["needs an SBA/VA certification you do not hold"]
    score += {"sb_set_aside": 35, "full_and_open": 15, "subcontract": 10}[ln]
    reasons.append({"sb_set_aside": "small-business set-aside", "full_and_open": "open competition",
                    "subcontract": "large prime: subcontract target"}[ln])
    amt = a["amount"]
    if amt <= MICRO:
        score += 15; reasons.append("micro-purchase size")
    elif amt <= SAT:
        score += 25; reasons.append("under $350k (simplified acquisition)")
    elif amt <= 2_000_000:
        score += 8; reasons.append("mid-size")
    end = dates.parse_date(a["end"])
    if end:
        days = (end - today).days
        if 90 <= days <= 365:
            score += 25; reasons.append(f"ends in {days} days: recompete prep window")
        elif 0 <= days < 90:
            score += 12; reasons.append(f"ends in {days} days: may already be re-solicited")
        elif days > 365:
            score += 5; reasons.append("ends after 12 months: watch")
        else:
            reasons.append("already ended")
    n = buyer_counts.get(a["sub_agency"], 0)
    if n >= 5:
        score += 15; reasons.append(f"repeat buyer ({n} awards in your NAICS)")
    elif n >= 2:
        score += 8; reasons.append(f"buys this {n}x")
    return min(score, 100), reasons


def buyers(awards):
    by = defaultdict(list)
    for a in awards:
        by[a["sub_agency"] or a["agency"]].append(a)
    rows = []
    for name, items in by.items():
        sb = sum(1 for a in items if a["tag"] == "sb_set_aside")
        rows.append({"buyer": name, "awards": len(items), "sb_set_aside": sb,
                     "median": statistics.median(a["amount"] for a in items)})
    return sorted(rows, key=lambda r: (-r["sb_set_aside"], -r["awards"]))


def incumbents(awards, today=None):
    today = today or dates.today()
    by = defaultdict(lambda: {"awards": 0, "total": 0.0, "active": 0})
    for a in awards:
        r = by[a["recipient"]]
        r["awards"] += 1
        r["total"] += a["amount"]
        end = dates.parse_date(a["end"])
        if end and end >= today:
            r["active"] += 1
    return sorted(({"recipient": k, **v} for k, v in by.items()), key=lambda r: (-r["active"], -r["total"]))


def load_cache(cache_dir=CACHE_DIR):
    """Newest fetch per tag. Returns (batches, provenance list)."""
    latest = {}
    for p in sorted(Path(cache_dir).glob("usaspending_*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        latest[doc["tag"]] = (doc, p)
    batches, prov = [], []
    for tag, (doc, p) in latest.items():
        batches.append((tag, doc["results"]))
        prov.append(f"{tag}: {len(doc['results'])} rows, fetched {doc['fetched_at']} from {doc['source_url']} ({p.name})")
    return batches, prov


def _money(x):
    return f"${x:,.0f}"


def report(awards, prov, today=None, top=25):
    today = today or dates.today()
    bc = defaultdict(int)
    for a in awards:
        bc[a["sub_agency"]] += 1
    live = [a for a in awards if (dates.parse_date(a["end"]) or today) >= today]
    ranked = sorted(((fit(a, bc, today), a) for a in live if lane(a) != "blocked"), key=lambda t: -t[0][0])
    blocked = [a for a in live if lane(a) == "blocked"]
    L = [f"# Bid finder: Georgia, NAICS {', '.join(NAICS)} (DRAFT)",
         f"Generated {today.isoformat()} by `python3 -m badgr_funding.bids report`. Offline ranking of cached USAspending data.",
         "Fit is a priority order for your attention, not a chance of winning.", "", "## Sources"]
    L += [f"- {p}" for p in prov] + ["", f"## Recompete watchlist (active awards, top {top} by fit)",
                                     "| Fit | Ends | Amount | Buyer | Incumbent | Lane | Competition | Why |", "|---|---|---|---|---|---|---|---|"]
    for (score, why), a in ranked[:top]:
        L.append(f"| {score} | {a['end']} | {_money(a['amount'])} | {a['sub_agency']} | {a['recipient']} | {lane(a)} | {competition_level(a)} | {'; '.join(why)} |")
    L += ["", "## Who buys your NAICS in Georgia (set-aside buyers first)", "| Buyer | Awards | SB set-aside | Median award |", "|---|---|---|---|"]
    for r in buyers(awards)[:15]:
        L.append(f"| {r['buyer']} | {r['awards']} | {r['sb_set_aside']} | {_money(r['median'])} |")
    L += ["", "## Incumbents: teaming and subcontract targets", "| Company | Active awards | Total | All awards |", "|---|---|---|---|"]
    for r in incumbents(awards, today)[:15]:
        L.append(f"| {r['recipient']} | {r['active']} | {_money(r['total'])} | {r['awards']} |")
    L += ["", f"## Blocked: certification set-asides ({len(blocked)} active)",
          "These need 8(a), HUBZone, WOSB, SDVOSB or VOSB status. Not ranked. Self-certified small is not 8(a).", "",
          "## Next steps", "- Pick 3 buyers from the set-aside table; ask APEX how each one posts work (SAM.gov, GSA eBuy, agency portal).",
          "- For recompetes in the 90-365 day window, watch SAM.gov for a sources-sought notice and answer it.",
          "- Email 2-3 incumbents with active awards about subcontracting; attach the capability statement."]
    return "\n".join(L) + "\n"


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="python3 -m badgr_funding.bids", description="Offline bid ranking from the local cache.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("--cache", default=str(CACHE_DIR))
    r.add_argument("--out", default=None)
    r.add_argument("--top", type=int, default=25)
    args = ap.parse_args(argv)
    batches, prov = load_cache(args.cache)
    if not batches:
        raise SystemExit(f"No cache in {args.cache}. Run: python3 -m badgr_funding.bidfetch usaspending --fetch")
    text = report(merge(batches), prov, top=args.top)
    out = Path(args.out or f"research/bids/BID_REPORT_{dates.today().isoformat()}.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
