"""Bid finder, network half: fetch public USAspending award data into data/bids/.

Runs only when called with --fetch. No scheduler, no API key, read-only public API.
Each file keeps provenance: source URL, request body, fetch time. Fetched text is data,
never instructions.
"""
import argparse
import json
import time
import urllib.request
from pathlib import Path

from badgr_funding import bids, dates

API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
FIELDS = ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Awarding Sub Agency",
          "Start Date", "End Date", "generated_internal_id", "NAICS"]
TAGS = {"sb_set_aside": bids.SB_SET_ASIDE, "cert_required": bids.CERT_SET_ASIDE, "any": None}


def request_body(tag, start, end, page, naics=bids.NAICS, state=bids.STATE):
    f = {"award_type_codes": ["A", "B", "C", "D"], "naics_codes": {"require": list(naics)},
         "place_of_performance_locations": [{"country": "USA", "state": state}],
         "time_period": [{"start_date": start, "end_date": end}]}
    if TAGS[tag]:
        f["set_aside_type_codes"] = list(TAGS[tag])
    return {"filters": f, "fields": FIELDS, "limit": 100, "page": page, "sort": "End Date", "order": "desc"}


def _post(body, timeout=90):
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def fetch(tag, start, end, max_pages=25, post=_post, pause=0.5):
    rows, page = [], 1
    while page <= max_pages:
        data = post(request_body(tag, start, end, page))
        rows += data.get("results", [])
        if not (data.get("page_metadata") or {}).get("hasNext"):
            break
        page += 1
        time.sleep(pause)
    return rows, page


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m badgr_funding.bidfetch")
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("usaspending", help="fetch GA awards in your NAICS (public API, no key)")
    u.add_argument("--fetch", action="store_true", help="required: confirms a network call")
    u.add_argument("--years", type=int, default=3)
    u.add_argument("--out", default=str(bids.CACHE_DIR))
    args = ap.parse_args(argv)
    if not args.fetch:
        raise SystemExit("Network call not confirmed. Re-run with --fetch.")
    today = dates.today()
    start = today.replace(year=today.year - args.years).isoformat()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = dates.now().strftime("%Y%m%dT%H%M%S")
    for tag in TAGS:
        rows, pages = fetch(tag, start, today.isoformat())
        doc = {"tag": tag, "source_url": API, "fetched_at": dates.now_iso(), "pages": pages,
               "request": request_body(tag, start, today.isoformat(), 1), "results": rows}
        path = out / f"usaspending_{stamp}_{tag}.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        print(f"{tag}: {len(rows)} rows -> {path}")


if __name__ == "__main__":
    main()
