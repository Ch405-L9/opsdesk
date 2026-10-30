# icp — the whole command list

One command, plain English, works from any directory.

## Discovery (the only thing that can cost money)
```
icp find me med spas in Lawrenceville GA
icp look for dentists in Duluth GA
icp find me fresh roofers in Gwinnett County     # "fresh" forces a paid refetch
```
First search for a given industry+city costs **1 Places call**. Repeating the
same search inside 14 days costs **nothing** — it reads the local cache.

## Full CRM workup (the main event)
```
icp enrich                 top 3 — audit, pain points, selling angle, email, call script
icp enrich 5               top 5
icp enrich verify          also verify the email with Hunter before sending
```
Writes `leads_enriched_<stamp>.csv` **and** `.xlsx` with every CRM field:
phone, best email, address, business type, Lighthouse scores worst-to-best,
ranked pain points with evidence, selling angle, estimated deal value,
ready-to-send cold email and call opener.

## Track what happened (this is what makes the scorer learn)
```
icp called Omni Family Dental
icp replied Lavender Med Spa
icp won Kontour
icp lost Bella Forever
```

## Shorthand
```
icp b      budget        icp t   top leads
icp k      keys          icp h   help
icp med spas in Lawrenceville GA        (no verb needed)
```

## Free — never costs a call
```
icp top leads              best stored prospects, ranked
icp what's my budget       remaining allowance on every provider
icp are my keys good       re-validate every key against its live endpoint
icp help
icp                        interactive; type naturally, Ctrl-D to exit
```

## Auditing
```
icp check billybutlerhvac.com
icp how fast is example.com
```
PageSpeed Insights, ~25,000/day free. Effectively unlimited.

## Ask Claude when stuck (always asks permission first)
```
<any harness command that fails>   -> offers "Ask Claude about it? [y/N]"
badgr "im stuck, ask claude"       -> escalate directly, any time
```
Logged to `state/escalations.log` so the answer is reusable.

## Same thing through the local agent
```
python3 ~/Projects/local_grown/badgr/harness.py "find me dentists in Duluth GA"
python3 ~/Projects/local_grown/badgr/harness.py "what's my api budget"
python3 ~/Projects/local_grown/badgr/harness.py           # interactive
```

## Original scripts still work
```
python3 src/root_scraper.py                      # Brave/Startpage chain
python3 src/free_scraper.py                      # DuckDuckGo, free, unmetered
```

## Maintenance
```
python3 tools/validate_keys.py       # re-check every key
python3 tools/build_keylist.py       # rebuild + fan out the 4 key files
~/my_env/bin/python -m pytest tests/ -q
```

## Where things live
```
~/.local/share/badgr/icp.db      leads, search cache, outcomes
state/api_usage.json             the spend ledger
config/providers.json            caps and spend posture
.env                             the operative keys
```

---

# Guardrails (automatic, but not a sandbox)

| Guard | What it does |
|---|---|
| **Budget ledger** | Refuses the call that would cross the monthly cap, *before* it is sent |
| **Counts on attempt** | A request that errors is still counted — providers bill those |
| **14-day cache** | A repeat search reads SQLite instead of billing |
| **Always request 20** | Cost is per request, not per result — never ask for fewer |
| **Cap = the real free tier** | `places.monthly_limit` is Google's actual 1,000 free Enterprise calls |
| **Corrupt ledger raises** | Never silently resets to "zero spent" and restarts your allowance |
| **No key → inert** | A missing key makes that provider refuse, not crash the run |
| **Keys in headers** | Brave/Places keys never appear in a URL or log |
| **Hard disqualifiers** | Franchise/OEM/captive-agent URLs scored 0 before any credit is spent |

**Honest caveat:** these are defaults, not a sandbox. The agent has
`run_command` with a real shell and can edit `config/providers.json`. They stop
accidents and runaway loops; they are not a security boundary against something
deliberately trying to get around them.

## Errors you may hit, and what they mean

| Message | Meaning | Fix |
|---|---|---|
| `would exceed this month's self-imposed cap` | The guardrail worked | Wait for reset, or raise `spend_posture` |
| `no API key. Set X in your environment` | Key missing from `.env` | `python3 tools/build_keylist.py` |
| `DuckDuckGo returned nothing` | Its anti-bot challenge fired (HTTP 202) | Use `icp find …` instead; free path is best-effort |
| `orchestrator error` / connection refused | Ollama is down | `systemctl --user status ollama` |
| `Need a location` | No city in the request | Add "in <city> <state>" |
| PSI returns no field data | Too little traffic for CrUX | Normal for small businesses; lab score still valid |
| `Requests to this API … are blocked` | API-key **restriction**, not a disabled API | Credentials → edit key → API restrictions |
| `project does not have access to Custom Search` | API closed to new customers, dead Jan 1 2027 | Nothing to fix. Don't chase it |
