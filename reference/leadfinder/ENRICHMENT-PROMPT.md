# Enrichment prompt

Copy everything below the line.

---

The ICP lead-generation system at `~/Projects/icp_intelligence` produces
CRM-grade prospect records. It is built, tested and running.

**Run it:** `icp enrich` (top 3 leads) — or `icp enrich 5`, or
`icp enrich verify` to also verify emails.

**Each record contains:** business name, phone, best email + verification
status, candidate emails, address, website, business type, vertical tier (A–D),
Google rating and review count, all four Lighthouse scores, LCP in seconds,
scores ordered worst-to-best, the four axis scores (need/ability/fit/reach),
priority 0–100, up to three ranked pain points with measured evidence, the
selling angle for the top pain, the service to sell, estimated deal value, a
ready-to-send cold email (subject + body) and a call opener.

**Output:** `leads_enriched_<timestamp>.csv` and `.xlsx` (formatted workbook,
frozen header, scores colour-banded red/amber/green).

**Grounding rule:** every claim traces to a number the system measured. No
invented revenue, traffic or competitor data. It never claims site speed
improves local-pack ranking, because that is unsupported.

Add this to the dashboard. Surface the enriched records, the pain-point
distribution, and the per-provider API budget. Read from
`~/.local/share/badgr/icp.db` and the exported CSV/XLSX.

Feel free to verify any of this before building.
