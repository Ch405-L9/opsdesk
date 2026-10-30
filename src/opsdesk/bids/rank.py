"""Offline bid ranking of cached USAspending awards. Scores are prioritization, never odds of winning."""

from __future__ import annotations

import datetime as dt
import statistics
from collections import defaultdict
from typing import Any

from opsdesk import timeutil

SB_SET_ASIDE = ("SBA", "SBP", "RSB", "ESB")
CERT_CODES: dict[str, tuple[str, ...]] = {
    "8a": ("8A", "8AN"),
    "hubzone": ("HZC", "HZS"),
    "sdvosb": ("SDVOSBC", "SDVOSBS"),
    "wosb": ("WOSB", "WOSBSS"),
    "edwosb": ("EDWOSB", "EDWOSBSS"),
    "vosb": ("VSA", "VSS"),
}
CERT_SET_ASIDE = tuple(code for codes in CERT_CODES.values() for code in codes)
SAT = 350_000      # simplified acquisition threshold (FAR, effective 2025-10-01)
MICRO = 15_000     # micro-purchase threshold (FAR, effective 2025-10-01)


def normalize(raw: dict[str, Any], tag: str) -> dict[str, Any]:
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
        "set_aside": raw.get("Set Aside Type") or raw.get("set_aside") or "",
        "tag": tag,
    }


def merge(batches: list[tuple[str, list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    """Dedupe by id; the most specific tag wins (cert > sb > any)."""
    rank = {"cert_required": 2, "sb_set_aside": 1, "any": 0}
    out: dict[str, dict[str, Any]] = {}
    for tag, rows in batches:
        for raw in rows:
            award = normalize(raw, tag)
            if not award["id"]:
                continue
            prev = out.get(award["id"])
            if prev is None or rank[tag] > rank[prev["tag"]]:
                out[award["id"]] = award
    return list(out.values())


def lane(award: dict[str, Any], eligibility: list[str] | None = None) -> str:
    held = {c.lower() for c in (eligibility or [])}
    if award["tag"] == "cert_required":
        codes = {c for k in held for c in CERT_CODES.get(k, ())}
        if award.get("set_aside") and award["set_aside"].upper() in codes:
            return "cert_eligible"
        return "blocked" if not held else "check_certification"
    if award["amount"] > 2_000_000:
        return "subcontract"
    if award["tag"] == "sb_set_aside":
        return "sb_set_aside"
    return "full_and_open"


LANE_POINTS = {"cert_eligible": 35, "sb_set_aside": 35, "check_certification": 15, "full_and_open": 15, "subcontract": 10}
LANE_REASON = {
    "cert_eligible": "certification set-aside you declared",
    "sb_set_aside": "small-business set-aside",
    "check_certification": "certification set-aside: confirm your certification matches",
    "full_and_open": "open competition",
    "subcontract": "large prime: subcontract target",
}


def fit(award: dict[str, Any], buyer_counts: dict[str, int], today: dt.date,
        eligibility: list[str] | None = None) -> tuple[int, list[str]]:
    ln = lane(award, eligibility)
    if ln == "blocked":
        return 0, ["needs an SBA/VA certification you have not declared (eligibility UNKNOWN)"]
    score, reasons = LANE_POINTS[ln], [LANE_REASON[ln]]
    amount = award["amount"]
    if amount <= MICRO:
        score += 15
        reasons.append("micro-purchase size")
    elif amount <= SAT:
        score += 25
        reasons.append("under the simplified acquisition threshold")
    elif amount <= 2_000_000:
        score += 8
        reasons.append("mid-size")
    end = timeutil.parse_date(award["end"])
    if end:
        days = (end - today).days
        if 90 <= days <= 365:
            score += 25
            reasons.append(f"ends in {days} days: recompete prep window")
        elif 0 <= days < 90:
            score += 12
            reasons.append(f"ends in {days} days: may already be re-solicited")
        elif days > 365:
            score += 5
            reasons.append("ends after 12 months: watch")
        else:
            reasons.append("already ended")
    n = buyer_counts.get(award["sub_agency"], 0)
    if n >= 5:
        score += 15
        reasons.append(f"repeat buyer ({n} awards in your NAICS)")
    elif n >= 2:
        score += 8
        reasons.append(f"buys this {n}x")
    return min(score, 100), reasons


def buyer_counts(awards: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for award in awards:
        counts[award["sub_agency"]] += 1
    return counts


def buyers(awards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for award in awards:
        by[award["sub_agency"] or award["agency"]].append(award)
    rows = [{"buyer": name, "awards": len(items),
             "sb_set_aside": sum(1 for a in items if a["tag"] == "sb_set_aside"),
             "median": statistics.median(a["amount"] for a in items)} for name, items in by.items()]
    return sorted(rows, key=lambda r: (-r["sb_set_aside"], -r["awards"]))


def incumbents(awards: list[dict[str, Any]], today: dt.date) -> list[dict[str, Any]]:
    by: dict[str, dict[str, Any]] = defaultdict(lambda: {"awards": 0, "total": 0.0, "active": 0})
    for award in awards:
        row = by[award["recipient"]]
        row["awards"] += 1
        row["total"] += award["amount"]
        end = timeutil.parse_date(award["end"])
        if end and end >= today:
            row["active"] += 1
    return sorted(({"recipient": k, **v} for k, v in by.items()), key=lambda r: (-r["active"], -r["total"]))
