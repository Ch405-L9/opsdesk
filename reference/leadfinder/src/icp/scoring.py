"""Multi-axis lead scoring.

The original scorer collapsed everything into `is_warm_prospect = bool(signals)`
where every signal measured NEED. That ranks a church (68.5% have unclaimed
Google profiles, no budget) identically to a med spa doing $2M a year.

Four axes are scored independently and combined multiplicatively, so a zero on
any axis sinks the lead instead of being averaged away:

  need     how broken their web presence is          -> is there work to sell
  ability  can they actually pay for it              -> revenue/size proxies
  fit      does their vertical match the offer       -> web opt + full stack dev
  reach    can a decision maker be contacted at all  -> phone, not corporate-run

Calibration note: these weights are REASONING, not measured coefficients. No
public research links any observable signal to an actual purchase. They are
priors to be replaced once ~30 real outcomes are logged.
"""
from __future__ import annotations

import re
from typing import Optional

AXES = ("need", "ability", "fit", "reach")

# Axis exponents. ability and fit dominate because the expensive mistake is
# spending a scarce Hunter credit on someone who was never going to buy.
_WEIGHTS = {"ability": 0.35, "fit": 0.25, "need": 0.25, "reach": 0.15}

# ── vertical tiers ────────────────────────────────────────────────────────────
# Ranked from market research: revenue per customer, documented marketing spend,
# and measured web quality. Tier A buys; tier D structurally cannot.
_TIERS = {
    "A": ["med_spa", "medspa", "aesthetics", "plastic_surgery", "cosmetic_dentistry",
          "dermatology", "dental_specialty", "orthodontist", "oral_surgeon",
          "law_estate", "law_immigration", "law_business", "financial_advisor",
          "insurance_agency", "cpa", "accountant", "bookkeeper"],
    "B": ["dentist", "veterinary", "vet", "chiropractor", "optometrist",
          "physical_therapy", "fertility", "med_practice", "real_estate_team"],
    "C": ["hvac", "roofing", "plumbing", "electrician", "landscaping", "pest_control",
          "garage_door", "flooring", "remodeling", "general_contractor", "gym", "fitness"],
    "D": ["hair_salon", "salon", "barber", "nail_salon", "restaurant", "cafe", "bar",
          "food_truck", "retail", "boutique", "photographer", "church", "nonprofit",
          "school", "government"],
}
_TIER_OF = {v: tier for tier, names in _TIERS.items() for v in names}
_TIER_POINTS = {"A": 100, "B": 72, "C": 48, "D": 10}

def vertical_tier(vertical: Optional[str]) -> str:
    """Tier for a vertical slug. Unknown verticals get C - neutral, not punished."""
    if not vertical:
        return "C"
    return _TIER_OF.get(str(vertical).strip().lower(), "C")

# ── hard disqualifiers ────────────────────────────────────────────────────────
_FRANCHISE_BRANDS = ("mightydog", "aireserv", "mrrooter", "rotorooter", "benjaminfranklin",
                     "mollymaid", "servpro", "chemdry", "1800", "neighborly", "aamco",
                     "mathnasium", "kumon", "snapfitness", "anytimefitness")
_DIRECTORY_OR_OEM = ("gaf.com", "carrier.com", "trane.com", "lennox.com", "owenscorning",
                     "angi.com", "thumbtack", "porch.com", "homeadvisor", "yelp.com",
                     "yellowpages", "bbb.org", "houzz.com", "networx", "mapquest")
_CAPTIVE = ("statefarm.com", "allstate.com", "edwardjones.com", "farmers.com",
            "americanfamily.com", "countryfinancial", "modernwoodmen")
# brand.com/<city>-<state>/ or /locations/<city> - the franchisee cannot buy a site
_FRANCHISE_PATH = re.compile(r"/(?:locations?|service-area|[a-z]+-(?:ga|al|tn|fl|sc|nc))(?:/|$)", re.I)

def disqualify(lead: dict) -> Optional[str]:
    """Return a reason code if this lead structurally cannot buy, else None."""
    if str(lead.get("status", "")).upper().startswith("CLOSED"):
        return "DORMANT"

    site = (lead.get("website") or "").lower()
    if not site:
        return None   # no website is the BEST signal - never filter it out

    host = re.sub(r"^https?://", "", site).split("/")[0]
    flat = host.replace("-", "").replace(".", "")

    if any(b in flat for b in _FRANCHISE_BRANDS):
        return "FRANCHISE_URL_PATTERN"
    if any(d in host for d in _DIRECTORY_OR_OEM):
        return "MANUFACTURER_OR_DIRECTORY"
    if any(c in host for c in _CAPTIVE):
        return "CAPTIVE_AGENT"
    if _FRANCHISE_PATH.search(site) and host.count(".") <= 2:
        # a national brand serving a city page, not a local business's own site
        if lead.get("review_count") is None or (lead.get("review_count") or 0) < 25:
            return "FRANCHISE_URL_PATTERN"
    return None

# ── axes ──────────────────────────────────────────────────────────────────────

def resolved_url(lead: dict, audit: Optional[dict]) -> Optional[str]:
    """The URL actually served, after redirects - or None if nobody measured it.

    NEVER fall back to lead["website"]. That is the Google Business Profile
    value, which is the stale http:// form for most businesses even when the
    site redirects to HTTPS. Trusting it produced a false "no HTTPS" claim on
    9 of 10 live leads, and that claim drives the email subject line.
    """
    if audit and audit.get("final_url"):
        return audit["final_url"]
    return lead.get("final_url")        # set by a cheap redirect probe, if run


def _need(lead: dict, audit: Optional[dict]) -> int:
    if not lead.get("has_website"):
        return 100                      # nothing beats having no website at all

    pts = 0
    final = resolved_url(lead, audit)
    if final and final.lower().startswith("http://"):
        pts += 25                       # genuinely insecure - rare, so a loud signal
    # No measured final URL -> make no SSL judgement at all. An unverified
    # claim in a cold email is worse than a missing one.

    if audit:
        perf = audit.get("performance")
        if perf is not None:
            # Google's own bands: <50 poor, 50-89 needs work, 90+ good.
            # The SMB average is 58, so almost everyone is in "needs work" -
            # absolute score is what matters, not the gap to average.
            pts += 55 if perf < 40 else 42 if perf < 50 else 28 if perf < 70 else 10 if perf < 90 else 0
        seo = audit.get("seo")
        if seo is not None:
            pts += 15 if seo < 60 else 8 if seo < 80 else 0
        lcp = audit.get("lcp_ms")
        if lcp:
            pts += 15 if lcp > 4000 else 8 if lcp > 2500 else 0
    else:
        pts += 20                       # unaudited: assume average, do not reward
    return min(100, pts)

def _ability(lead: dict) -> int:
    """Revenue proxies for THIS business. Review count is the best public one.

    Vertical tier deliberately does NOT appear here. It used to contribute 55
    points, while also being 100% of `fit` - so tier carried an effective
    weight of ~0.60 instead of the documented 0.25, and the pre-audit ranking
    was essentially a vertical lookup table. Tier now lives in `fit` only.
    """
    pts = 10                            # a real, operating business

    n = lead.get("review_count") or 0
    pts += 55 if n >= 500 else 44 if n >= 200 else 32 if n >= 75 else 20 if n >= 25 else 8 if n >= 5 else 0

    r = lead.get("rating") or 0
    if r >= 4.5 and n >= 25:
        pts += 20                       # established and well regarded
    elif r >= 4.0 and n >= 10:
        pts += 10
    if lead.get("multi_location"):
        pts += 15                       # 2+ locations implies real budget
    return int(min(100, pts))

def _fit(lead: dict) -> int:
    return _TIER_POINTS[vertical_tier(lead.get("vertical"))]

def _reach(lead: dict) -> int:
    pts = 40
    if lead.get("phone"):
        pts += 35
    if lead.get("has_website"):
        pts += 15                       # a site usually means a contact form
    if lead.get("address"):
        pts += 10
    return min(100, pts)

# ── combine ───────────────────────────────────────────────────────────────────

def score_lead(lead: dict, audit: Optional[dict] = None) -> dict:
    reason = disqualify(lead)
    axes = {"need": _need(lead, audit), "ability": _ability(lead),
            "fit": _fit(lead), "reach": _reach(lead)}

    if reason:
        return {**axes, "priority": 0, "disqualified": reason}

    # Weighted geometric mean: a zero on any axis sinks the lead. An arithmetic
    # mean would let a perfect need score hide a total inability to pay.
    product = 1.0
    for axis, weight in _WEIGHTS.items():
        product *= max(axes[axis], 1) ** weight
    return {**axes, "priority": int(round(min(100.0, product))), "disqualified": None}
