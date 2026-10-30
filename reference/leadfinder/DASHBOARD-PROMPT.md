# Dashboard prompt

Copy everything below the line and give it to the frontier model.

---

The icp_intelligence lead-generation system is built, tested and running at
`~/Projects/icp_intelligence`. I need you to add it to the dashboard.

**What it does**
Finds local businesses by category and geography, scores them as sales
prospects on four axes, audits their websites with real Lighthouse data,
extracts evidence-backed pain points with a selling angle and estimated deal
value, and drafts a cold email and call opener for each.

**What is built and verified**
- Natural-language CLI installed globally as `icp`, works from any directory:
  `icp find me med spas in Lawrenceville GA`, `icp enrich`, `icp t`, `icp b`,
  `icp check example.com`, `icp called <business>`.
- 8 validated API keys. Google Places for discovery, PageSpeed Insights for
  auditing, plus Brave, Firecrawl, SerpApi, Hunter (verification only),
  Abstract and Upgini. Each confirmed live against its endpoint.
- Four-axis scoring (ability .35, fit .25, need .25, reach .15) combined by
  weighted geometric mean, with hard disqualifiers for franchise, directory and
  captive-agent URLs.
- Pain-point engine producing seven typed findings, each with measured
  evidence, a selling angle, the service to sell and an estimated value range.
- CSV and formatted XLSX export, 38 CRM fields per record.
- SQLite at `~/.local/share/badgr/icp.db`: `leads` (ranked, host-keyed),
  `search_cache` (14-day TTL), `outcomes` (event log).
- Budget ledger at `state/api_usage.json`, per-provider monthly caps.
- Wired into a local 4B agent via `~/Projects/local_grown/badgr/harness.py`.
- 128 automated tests, all passing, all offline.

**Live data already collected**
40 scored businesses across med spas in Lawrenceville GA and dentists in
Duluth GA, every one with a direct phone number. Top prospect scores 90 of 100
and has no website at all.

**What I want**
Add this to the dashboard. Surface the ranked leads with their four axis
scores, the pain-point distribution, the per-provider API budget remaining,
and the outcome counts. Read from `~/.local/share/badgr/icp.db` and
`state/api_usage.json`.

Two things to carry through rather than smooth over: the scoring weights are
market priors, not measured coefficients, until ~30 outcomes are logged; and
before enrichment the `need` axis is a placeholder, so discovery ranking is
mostly vertical tier plus review count. Show measured and unmeasured
differently.

Feel free to verify any of this before you build.
