"""Deterministic natural-language intent router.

This runs BEFORE the local model. The local_grown design note puts it plainly:
"Known commands can bypass model interpretation." Every phrasing matched here
costs no inference, cannot be mis-parsed, and works whether or not Ollama is
running. Anything it does not recognise returns intent "unknown" and the caller
hands it to badgr-orchestrator.

Add phrasings here rather than widening the model prompt - a regex that matches
is always faster and more reliable than a 4B model that usually matches.
"""
from __future__ import annotations

import re
from typing import Optional

# Verbs that introduce a discovery request.
_FIND_VERB = r"(?:find|search(?:\s+for)?|look(?:\s+for|\s+up)?|get(?:\s+me)?|show(?:\s+me)?|discover|list|pull(?:\s+up)?|scrape)"
_AUDIT_VERB = r"(?:audit|check|score|test|analy[sz]e|run\s+pagespeed\s+on|how\s+fast\s+is|speed\s+test)"

_DOMAIN = r"\b((?:https?://)?(?:[a-z0-9][a-z0-9\-]*\.)+[a-z]{2,}(?:/[^\s]*)?)\b"

def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().strip("!?.,").lower())

def _normalise_url(raw: str) -> str:
    raw = raw.strip().rstrip(".,")
    return raw if raw.startswith(("http://", "https://")) else "https://" + raw

def _singular(phrase: str) -> str:
    """'med spas' -> 'med spa'. Crude, but these are search terms, not grammar."""
    phrase = phrase.strip()
    if phrase.endswith("ies") and len(phrase) > 4:
        return phrase[:-3] + "y"
    if phrase.endswith("ses") or phrase.endswith("xes") or phrase.endswith("zes"):
        return phrase[:-2]
    if phrase.endswith("s") and not phrase.endswith("ss"):
        return phrase[:-1]
    return phrase

def route(text: str) -> dict:
    t = _clean(text)
    if not t:
        return {"intent": "help"}

    # --- single-letter shortcuts (typed constantly, so make them one key) ----
    _SHORT = {"b": "budget", "$": "budget", "t": "top", "l": "top",
              "k": "keys", "h": "help", "?": "help"}
    if t in _SHORT:
        return {"intent": _SHORT[t]}

    # --- help ---------------------------------------------------------------
    if re.fullmatch(r"(help|commands?|what can (you|u) do|how do i use (this|it)|\?)", t):
        return {"intent": "help"}

    # --- enrich: full CRM workup on the top N ------------------------------
    m = re.search(r"\b(enrich|work\s*up|full\s+(?:report|detail)|deep\s+dive|pain\s*points?)\b", t)
    if m:
        num = re.search(r"\b(\d{1,2})\b", t)
        return {"intent": "enrich",
                "limit": int(num.group(1)) if num else 3,     # 3 = a day of calls
                "verify": bool(re.search(r"\bverif", t))}

    # --- stored leads (free - reads the local database) ---------------------
    if re.search(r"\b(top|best|stored|saved|my)\s+(leads?|prospects?)\b", t) or t in {"leads", "top leads"}:
        return {"intent": "top"}

    # --- budget / spend -----------------------------------------------------
    if re.search(r"\b(budget|credits?|quota|allowance|spent|spend|usage|how much.*(left|used))\b", t):
        return {"intent": "budget"}

    # --- keys ---------------------------------------------------------------
    if re.search(r"\b(keys?|api keys?|credentials?)\b", t) and not re.search(r"\bfind\b.*\bin\b", t):
        return {"intent": "keys"}

    # --- audit: an explicit verb with a domain, or a bare domain ------------
    m = re.search(rf"{_AUDIT_VERB}\s+(?:on\s+)?{_DOMAIN}", t)
    if m:
        return {"intent": "audit", "url": _normalise_url(m.group(1))}
    if re.fullmatch(_DOMAIN, t):
        return {"intent": "audit", "url": _normalise_url(t)}

    # --- find: "<verb> [me] <industry> in <location>" ------------------------
    m = re.search(rf"{_FIND_VERB}\s+(?:me\s+)?(?:some\s+|all\s+|the\s+)?(.+?)(?:\s+in\s+(.+))?$", t)
    if m:
        industry = _singular(re.sub(r"^(some|all|the)\s+", "", m.group(1).strip()))
        location = (m.group(2) or "").strip() or None
        if industry:
            # "fresh"/"again" forces a paid refetch instead of using the cache
            fresh = bool(re.search(r"\b(fresh|again|refresh|re-?fetch|latest)\b", t))
            industry = re.sub(r"\b(fresh|again|refresh|re-?fetch|latest)\b", "", industry).strip()
            return {"intent": "find", "industry": industry, "location": location, "fresh": fresh}

    # Bare "<industry> in <city>" with no verb at all - the shortest useful form.
    # Guarded: these verbs mean the user wants prose, not a business search, and
    # an unguarded "X in Y" happily swallows "write me a poem about roofing in
    # iambic pentameter". Those belong to the model, not here.
    _PROSE_VERB = r"^(write|tell|explain|make|generate|create|draft|compose|draw|summari[sz]e|translate|describe|what|why|how|who|when|should|can|could|would|is|are|does)\b"
    m = None if re.match(_PROSE_VERB, t) else re.fullmatch(r"(.+?)\s+in\s+(.+)", t)
    # A location is a few words, not a clause.
    if m and len(m.group(1)) < 40 and len(m.group(2).split()) <= 4:
        fresh = bool(re.search(r"\b(fresh|again|refresh)\b", t))
        return {"intent": "find", "industry": _singular(m.group(1).strip()),
                "location": m.group(2).strip(), "fresh": fresh}

    # --- outcome logging: "called X", "won X", "lost X" ---------------------
    m = re.match(r"(?:log\s+)?(called|contacted|emailed|replied|meeting|proposal|won|lost)\s+(.+)",
                 t)
    if m:
        event = {"emailed": "contacted", "called": "contacted"}.get(m.group(1), m.group(1))
        return {"intent": "outcome", "event": event, "target": m.group(2).strip()}

    return {"intent": "unknown", "text": text}
