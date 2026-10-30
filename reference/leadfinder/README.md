# icp_intelligence

Finds local businesses, scores them as sales prospects, audits their websites
with real Lighthouse data, extracts evidence-backed pain points, and drafts
outreach. Driven by plain English, from any directory, or by a local model.

```bash
icp find me med spas in Lawrenceville GA
icp enrich                 # top 3: audit + pain points + email + call script
icp t                      # best stored prospects
icp b                      # API budget remaining
```

---

## The rule everything is built around

**Every claim made to a prospect must trace to a number this system measured.**

"Your site is slow" is a guess. "Your mobile Lighthouse score is 31/100 and
your largest element takes 6.2 seconds to paint" is a fact they can verify.
The second is why a paid audit is sellable.

This is not decoration. It has already caught a real failure: the system used
to decide "no HTTPS" from a URL prefix, and **9 of 10 live leads flagged that
way actually served working HTTPS** — because Google Places stores whatever
the owner typed into their profile years ago. That claim drove the email
subject line. It now comes from PageSpeed's measured `finalUrl`, or it is not
made at all.

Two things it will never say:
- **Speed improves local-pack ranking.** A 4,500-landing-page study found Core
  Web Vitals did not improve local rankings. Speed is sold on conversion and
  ad cost.
- **Anything resembling legal advice** on accessibility. Risk and reach only.

---

## How a lead is scored

Four axes, combined by **weighted geometric mean** (weights sum to 1.0), which
is less compensatory than an average — a weak axis only partly offsets strong
ones.

| Axis | Weight | Measures |
|---|---|---|
| ability | 0.35 | review volume, rating, multi-location |
| fit | 0.25 | vertical tier A–D |
| need | 0.25 | no website, Lighthouse bands, verified no-SSL, slow LCP |
| reach | 0.15 | phone, address, not corporate-controlled |

**Need is not the same as buyer.** Hair salons have the worst web presence of
47 industries measured *and* the lowest ad budget of 11 sectors. Churches have
the highest unclaimed-Google-Profile rate at 68.5%. Maximum need, no money.
The old scorer ranked them as prime leads; this one sinks a church to 17
against a med spa's 90.

**Honest limits:**
- A zero on an axis **heavily penalises but does not eliminate** — ability=0
  caps priority near 20, not 0.
- Every weight is a **market prior, not a measured coefficient.** No public
  research links an observable signal to an actual purchase. `icp called X` /
  `icp won X` logs outcomes; at ~30 the weights can be replaced with your own.
- Before `icp enrich`, `need` is a placeholder. Discovery ranking is mostly
  tier plus review count.

---

## Providers

| Provider | Free allowance | Role |
|---|---|---|
| **Google Places** | **1,000 calls/mo** | **Discovery. The only one that can bill you.** |
| PageSpeed Insights | ~25,000/day | Auditing. Effectively unlimited |
| Brave Search | 2,000/mo | SERP. **Legacy key — irreplaceable** |
| Firecrawl | 1,000 credits | JS rendering |
| SerpApi | 250/mo | Ranking checks |
| Hunter.io | 50 search / 100 verify | **Verifier, not a search tool** |

**The Places math:** it bills at Text Search **Enterprise** ($35/1,000 after
the free tier) because the field mask needs website + phone + rating + reviews,
and Google bills at the highest SKU of any requested field. One call returns 20
businesses, so 800 usable calls ≈ 16,000 businesses/month, free. A repeat
search inside 14 days hits the cache and costs nothing.

**Why Places and not a search engine:** SERP results are businesses that
already rank — structurally the ones who least need help. Places enumerates by
category and geography, so it returns businesses with **no website at all**.
Those are consistently the highest-scoring leads, and no SERP can surface them.

---

## The local model

`badgr-orchestrator` (Huihui-Qwen3-4B-Instruct, Q4_K_M, ~44 tok/s, fits 4GB
VRAM) on Ollama, driven by `~/Projects/local_grown/badgr/harness.py`. Natural
language in, one JSON command out, harness executes. The model never executes
anything itself.

Tools: `web_research`, `web_scrape`, `top_leads`, `enrich_leads`, `api_budget`,
`log_outcome`, `escalate`, plus the pre-existing file and shell tools.

**Routing is two layers.** A deterministic regex router resolves known
phrasings with zero inference; the model is the fallback. This is the project's
own rule — *"Known commands can bypass model interpretation."* It also survives
Ollama being down.

**Escalation.** Any failing tool offers to hand the task to Claude. It always
asks permission first, and logs to `state/escalations.log`.

**A protection worth preserving:** the 4B model cannot be prompt-injected by
scraped content, because `orchestrate` never feeds tool output back as a model
turn. If a tool-result turn is ever added so the model can read its own output,
that protection disappears and any prospect's website could steer it.

---

## Layout

```
src/icp/        cli, nl, discovery, audit, scoring, painpoints,
                outreach, enrich, store, budget, providers, ddg
src/root_scraper.py    Brave → Startpage → Mojeek → DuckDuckGo chain
src/free_scraper.py    DuckDuckGo, free and unmetered
tests/                 128 tests, all offline
tools/                 validate_keys.py, build_keylist.py
config/providers.json  caps, spend posture, verified quota provenance
siteaudit/             local Lighthouse CLI (`siteaudit audit <url>`)
~/.local/share/badgr/icp.db    leads, search cache, outcomes
```

**Docs:** `COMMANDS.md` (every command + guardrails + error table) ·
`HANDOFF.md` (root causes and reasoning) · `BUILD-LOG.md` (exact terminal
commands, including the failures, as training material) ·
`DASHBOARD-PROMPT.md` · `ENRICHMENT-PROMPT.md`

**Setup:** `~/my_env/bin/python` — pandas 3.1.0, pydantic 2.14.1, requests,
bs4, loguru, playwright, openpyxl. `upgini` pins `pandas<3` and must stay in
its own venv or it breaks `root_scraper.py`.

```bash
~/my_env/bin/python -m pytest tests/ -q
```

---

## Things that have actually bitten

- **DuckDuckGo: POST works, GET returns a 202 challenge.** This is also why
  driving a headless browser at it fails — navigation is a GET.
- **Never trust vendor docs for quota.** They were wrong in both directions for
  Hunter. Use the free status endpoints: `serpapi.com/account`,
  `api.hunter.io/v2/account`, `api.firecrawl.dev/v1/team/credit-usage`.
- **`grep … | head` in a test always exits 0** — a pipeline's status is the
  last command's. This silently broke a credential scan.
- **Google Custom Search is closed to new customers**, dead Jan 1 2027. Three
  keys, three projects, three 403s. Not fixable.
- **Hunter is a verifier.** Two 1,000-review med spas returned zero and one
  generic address. Places gives a phone number for ~100% of businesses, free.
