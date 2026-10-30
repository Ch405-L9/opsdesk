"""Cold email and call-opener drafts, grounded only in measured evidence.

Hard rule: every claim in a draft traces to a number this system actually
measured. No invented revenue, no invented traffic, no "we noticed you're
losing customers". The prospect can verify every sentence, which is the whole
reason a paid audit is sellable.

Also never claims that site speed improves local/map-pack ranking - that is
unsupported (Whitespark, 4,500 landing pages). Speed is sold on conversion
and ad cost.
"""
from __future__ import annotations

from typing import List, Optional

from .painpoints import band, headline_pain, scores_worst_to_best

SENDER = {"name": "Anthony", "company": "BADGR Labs", "area": "Gwinnett County"}

def subject_line(lead: dict, pains: List[dict]) -> str:
    p = headline_pain(pains)
    name = lead.get("name", "your business")
    if not p:
        return f"Quick question about {name}'s website"
    if p["code"] == "NO_WEBSITE":
        return f"{name} has {lead.get('review_count') or 'great'} reviews and no website"
    if p["code"] == "NO_SSL":
        return f"{name}'s site shows a 'Not secure' warning"
    if p["code"] in ("SLOW_MOBILE", "SLOW_LCP"):
        return f"{name}'s site scores {lead.get('_perf', '?')}/100 on mobile"
    if p["code"] == "ACCESSIBILITY":
        return f"An accessibility issue on {name}'s site"
    return f"Something I noticed on {name}'s site"

def cold_email(lead: dict, audit: Optional[dict], pains: List[dict],
               sender: dict = None) -> dict:
    """Short, specific, one ask. Long emails from strangers do not get read."""
    s = {**SENDER, **(sender or {})}
    name = lead.get("name", "there")
    p = headline_pain(pains)

    if not p:
        body = (f"Hi,\n\nI ran a Google Lighthouse audit on {name}'s site and it came back "
                f"clean - genuinely better than most {s['area']} businesses I look at.\n\n"
                f"Nothing to sell you here. If you ever want a second pair of eyes, I'm local.\n\n"
                f"- {s['name']}, {s['company']}")
        return {"subject": f"{name}'s site checks out", "body": body, "pain_code": None}

    scores = scores_worst_to_best(audit)
    score_line = ""
    if scores:
        worst = ", ".join(f"{k} {v}/100" for k, v in scores[:3])
        score_line = f"\nFull audit, worst first: {worst}.\n"

    if p["code"] == "NO_WEBSITE":
        opener = (f"You've got {lead.get('review_count') or 'a lot of'} Google reviews at "
                  f"{lead.get('rating') or 'a strong rating'} - and no website. Anyone who "
                  f"searches for you lands on a Maps pin or a competitor.")
    else:
        opener = (f"I ran a Google Lighthouse audit on {lead.get('website')} this week. "
                  f"{p['headline']}.")

    body = (
        f"Hi,\n\n"
        f"{opener}\n"
        f"{score_line}"
        f"\n{p['evidence']}\n\n"
        f"I'm local to {s['area']} and I fix exactly this. Typical range for the work is "
        f"{p['est_value']}, and I'd start by showing you the full report so you can decide "
        f"if it's worth doing at all.\n\n"
        f"Worth a 10-minute call this week?\n\n"
        f"- {s['name']}, {s['company']}\n"
    )
    return {"subject": subject_line({**lead, "_perf": (audit or {}).get("performance")}, pains),
            "body": body, "pain_code": p["code"]}

def call_opener(lead: dict, audit: Optional[dict], pains: List[dict]) -> str:
    """What to say in the first 15 seconds. Lead with the number."""
    p = headline_pain(pains)
    name = lead.get("name", "you")
    if not p:
        return (f"Hi, this is {SENDER['name']} with {SENDER['company']} here in "
                f"{SENDER['area']}. I audit local business websites - yours actually "
                f"scored well, so I'm not calling to sell you anything.")
    if p["code"] == "NO_WEBSITE":
        return (f"Hi, this is {SENDER['name']} with {SENDER['company']}, local to "
                f"{SENDER['area']}. I noticed {name} has "
                f"{lead.get('review_count') or 'a lot of'} Google reviews but no website - "
                f"is that on purpose, or just something that never got done?")
    perf = (audit or {}).get("performance")
    return (f"Hi, this is {SENDER['name']} with {SENDER['company']}, local to "
            f"{SENDER['area']}. I ran a free Google Lighthouse test on your site this "
            f"morning - it came back {perf}/100 on mobile, where 90 is the pass mark. "
            f"Do you have 30 seconds for me to tell you the one thing hurting it most?")
