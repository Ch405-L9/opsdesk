"""Bid workflow: fetch into a local cache, import into the workbench, rank and report."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from opsdesk import timeutil
from opsdesk.bids import fetch as fetchmod
from opsdesk.bids.rank import buyer_counts, buyers, fit, incumbents, lane, merge
from opsdesk.paths import AppPaths
from opsdesk.profile import load_profile
from opsdesk.workbench import add_source, list_items, log, upsert_item, workbench

TERMS = "USAspending.gov public award data (U.S. Treasury); no key required"


def cache_dir(paths: AppPaths) -> Path:
    return paths.data_dir / "bids"


def plan_fetch(paths: AppPaths, years: int = 3) -> dict[str, Any]:
    profile = load_profile(paths.profile_file)
    return {"naics": profile.naics_codes, "state": profile.home_state, "years": years,
            "requests": f"up to {3 * 25} public API pages (no key, no cost)",
            "ready": bool(profile.naics_codes)}


def fetch(paths: AppPaths, years: int = 3, *, post: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
          pause: float = 0.5) -> dict[str, int]:
    profile = load_profile(paths.profile_file)
    if not profile.naics_codes:
        raise ValueError("Add your NAICS codes first: `opsdesk init` (e.g. 541511 for custom programming).")
    today = timeutil.today(profile.timezone)
    start = today.replace(year=today.year - years).isoformat()
    out = cache_dir(paths)
    out.mkdir(parents=True, exist_ok=True)
    stamp = timeutil.now(profile.timezone).strftime("%Y%m%dT%H%M%S")
    counts: dict[str, int] = {}
    for tag in fetchmod.TAGS:
        kwargs: dict[str, Any] = {"pause": pause}
        if post is not None:
            kwargs["post"] = post
        rows, pages = fetchmod.fetch(tag, start, today.isoformat(), profile.naics_codes, profile.home_state, **kwargs)
        doc = {"tag": tag, "source_url": fetchmod.API, "fetched_at": timeutil.now_iso(profile.timezone),
               "pages": pages, "naics": profile.naics_codes, "state": profile.home_state, "results": rows}
        (out / f"usaspending_{stamp}_{tag}.json").write_text(json.dumps(doc), encoding="utf-8")
        counts[tag] = len(rows)
    sync(paths)
    return counts


def load_cache(paths: AppPaths) -> tuple[list[tuple[str, list[dict[str, Any]]]], list[str]]:
    latest: dict[str, tuple[dict[str, Any], Path]] = {}
    for p in sorted(cache_dir(paths).glob("usaspending_*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        latest[doc["tag"]] = (doc, p)
    batches = [(tag, doc["results"]) for tag, (doc, _) in latest.items()]
    prov = [f"{tag}: {len(doc['results'])} rows fetched {doc['fetched_at']} from {doc['source_url']}"
            for tag, (doc, _) in latest.items()]
    return batches, prov


def sync(paths: AppPaths) -> dict[str, int]:
    """Import the newest cache into the workbench. Never touches workflow fields."""
    profile = load_profile(paths.profile_file)
    batches, prov = load_cache(paths)
    awards = merge(batches)
    today = timeutil.today(profile.timezone)
    counts_by_buyer = buyer_counts(awards)
    tally = {"inserted": 0, "updated": 0, "unchanged": 0}
    with workbench(paths) as conn:
        src = add_source(conn, "bids", "cache", "; ".join(prov) or "empty", TERMS)
        for award in awards:
            score, reasons = fit(award, counts_by_buyer, today, profile.set_aside_eligibility)
            payload = {**award, "lane": lane(award, profile.set_aside_eligibility), "fit": score,
                       "reasons": reasons, "url": f"https://www.usaspending.gov/award/{award['id']}"}
            tally[upsert_item(conn, f"bid:usaspending:{award['id']}", payload, src)] += 1
        log(conn, "bids.sync", None, tally)
    return tally


def ranked(paths: AppPaths, top: int = 25) -> list[dict[str, Any]]:
    profile = load_profile(paths.profile_file)
    today = timeutil.today(profile.timezone)
    with workbench(paths) as conn:
        items = list_items(conn, "bid", limit=5000)
    live = [i for i in items if (timeutil.parse_date(i.get("end")) or today) >= today and i.get("lane") != "blocked"]
    return sorted(live, key=lambda i: -int(i.get("fit") or 0))[:top]


def report(paths: AppPaths, top: int = 25) -> str:
    profile = load_profile(paths.profile_file)
    today = timeutil.today(profile.timezone)
    batches, prov = load_cache(paths)
    awards = merge(batches)
    money = lambda x: f"${x:,.0f}"  # noqa: E731
    lines = [f"# Bid report: {profile.home_state or 'all states'}, NAICS {', '.join(profile.naics_codes) or '-'}",
             f"Generated {today.isoformat()} by OpsDesk from cached USAspending data.",
             "Fit is a priority order for your attention, not a chance of winning.", "", "## Sources"]
    lines += [f"- {p}" for p in prov] or ["- (no cache yet: run `opsdesk bids fetch`)"]
    lines += ["", f"## Recompete watchlist (top {top})", "| Fit | Ends | Amount | Buyer | Incumbent | Lane | Why |",
              "|---|---|---|---|---|---|---|"]
    for i in ranked(paths, top):
        lines.append(f"| {i['fit']} | {i['end']} | {money(i['amount'])} | {i['sub_agency']} | {i['recipient']} | "
                     f"{i['lane']} | {'; '.join(i['reasons'])} |")
    lines += ["", "## Repeat buyers", "| Buyer | Awards | SB set-aside | Median |", "|---|---|---|---|"]
    lines += [f"| {r['buyer']} | {r['awards']} | {r['sb_set_aside']} | {money(r['median'])} |" for r in buyers(awards)[:15]]
    lines += ["", "## Incumbents (teaming / subcontract targets)", "| Company | Active | Total | All |", "|---|---|---|---|"]
    lines += [f"| {r['recipient']} | {r['active']} | {money(r['total'])} | {r['awards']} |" for r in incumbents(awards, today)[:15]]
    return "\n".join(lines) + "\n"
