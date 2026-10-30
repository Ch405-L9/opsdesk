"""Tests for the natural-language intent router.

The router is deterministic and runs BEFORE the local model. Anything it
recognises skips the model entirely - zero latency, zero chance of a bad parse.
The model is the fallback for phrasings it does not know.
"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from icp.nl import route

def test_budget_phrasings():
    for text in ["whats my budget", "what's my budget?", "budget", "how many credits left",
                 "show me my credits", "how much have i spent", "api usage"]:
        assert route(text)["intent"] == "budget", text

def test_keys_phrasings():
    for text in ["are my keys good", "check my keys", "validate keys", "keys", "test the api keys"]:
        assert route(text)["intent"] == "keys", text

def test_find_extracts_industry_and_location():
    r = route("find me med spas in Lawrenceville GA")
    assert r["intent"] == "find"
    assert "med spa" in r["industry"].lower()
    assert "lawrenceville" in r["location"].lower()

def test_find_alternate_verbs():
    for verb in ["find", "search for", "look for", "get me", "show me", "discover"]:
        r = route(f"{verb} dentists in Duluth GA")
        assert r["intent"] == "find", verb
        assert "duluth" in r["location"].lower(), verb

def test_audit_detects_bare_domain():
    r = route("check billybutlerhvac.com")
    assert r["intent"] == "audit"
    assert r["url"] == "https://billybutlerhvac.com"

def test_audit_detects_full_url():
    r = route("how fast is https://example.com/page")
    assert r["intent"] == "audit"
    assert r["url"] == "https://example.com/page"

def test_audit_phrasings():
    for text in ["audit example.com", "score example.com", "run pagespeed on example.com"]:
        assert route(text)["intent"] == "audit", text

def test_help_phrasings():
    for text in ["help", "what can you do", "commands"]:
        assert route(text)["intent"] == "help", text

def test_unknown_falls_through_to_model():
    r = route("write me a poem about roofing in iambic pentameter")
    assert r["intent"] == "unknown", r

def test_find_without_location_is_still_find():
    r = route("find me some plumbers")
    assert r["intent"] == "find"
    assert r["location"] in (None, "")

def test_router_is_case_and_punctuation_insensitive():
    assert route("  BUDGET!!  ")["intent"] == "budget"


def test_top_leads_phrasings():
    for text in ["top leads", "best leads", "show me my top prospects", "stored leads"]:
        assert route(text)["intent"] == "top", text

def test_fresh_forces_refetch():
    assert route("find me fresh med spas in Lawrenceville GA")["fresh"] is True
    assert route("find me med spas in Lawrenceville GA")["fresh"] is False


def test_single_letter_shortcuts():
    assert route("b")["intent"] == "budget"
    assert route("t")["intent"] == "top"
    assert route("k")["intent"] == "keys"
    assert route("h")["intent"] == "help"

def test_bare_industry_in_city_needs_no_verb():
    r = route("med spas in Lawrenceville GA")
    assert r["intent"] == "find"
    assert "med spa" in r["industry"]
    assert "lawrenceville" in r["location"].lower()

def test_outcome_logging_phrasings():
    assert route("called Omni Family Dental") == {"intent": "outcome", "event": "contacted", "target": "omni family dental"}
    assert route("won Lavender Med Spa")["event"] == "won"
    assert route("lost Kontour")["event"] == "lost"


def test_prose_requests_still_fall_through_to_model():
    for text in ["write me a poem about roofing in iambic pentameter",
                 "explain how caching works in python",
                 "what is the best approach in this situation"]:
        assert route(text)["intent"] == "unknown", text

def test_long_location_clause_is_not_treated_as_a_place():
    assert route("the thing i was talking about in the meeting we had yesterday")["intent"] == "unknown"


def test_enrich_defaults_to_three():
    r = route("enrich")
    assert r["intent"] == "enrich" and r["limit"] == 3 and r["verify"] is False

def test_enrich_respects_explicit_count_and_verify():
    assert route("enrich 5")["limit"] == 5
    assert route("enrich 2 and verify the emails")["verify"] is True

def test_pain_points_phrasing_triggers_enrich():
    assert route("give me the pain points")["intent"] == "enrich"
