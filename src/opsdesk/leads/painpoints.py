"""Turn measured audit data into pain points and the selling angle for each.

Rule this module exists to enforce: every pain point must be backed by a NUMBER
we actually measured. "Your site is slow" is a guess. "Your mobile Lighthouse
score is 31/100 and your largest element takes 6.2 seconds to paint" is a fact
the prospect can verify, and it is what makes a paid audit credible.

Three things are deliberately NOT claimed:
  * We never claim speed improves Google Maps/local-pack ranking. A 4,500-page
    Whitespark study found Core Web Vitals did NOT improve local pack rankings.
    Speed is sold on conversion and ad quality score instead.
  * We never invent revenue numbers for a prospect.
  * Accessibility is framed as risk + reach, never as legal advice.
"""
from __future__ import annotations


# Google's own Lighthouse bands.
def band(score: int | None) -> str:
    if score is None:
        return "unknown"
    return "poor" if score < 50 else "needs work" if score < 90 else "good"

def _p(code, severity, headline, evidence, angle, service, value):
    return {"code": code, "severity": severity, "headline": headline,
            "evidence": evidence, "angle": angle, "service": service, "est_value": value}

def pain_points(lead: dict, audit: dict | None) -> list[dict]:
    """Return pain points ordered worst-first. Each carries its own evidence."""
    out: list[dict] = []

    # ---- no website at all: the single biggest gap ---------------------------
    if not lead.get("has_website"):
        rc = lead.get("review_count") or 0
        out.append(_p(
            "NO_WEBSITE", 100,
            "No website at all",
            f"Google Business Profile is live with {rc} reviews, but there is no website "
            f"to send that traffic to. Every search for this business ends at a Maps "
            f"listing or a competitor.",
            "They have already earned the reputation - they just have nowhere to convert it. "
            "This is the easiest 'before and after' in the business.",
            "Full website build", "$2,500-$8,000"))
        return out   # nothing else is measurable without a site

    # Only from a MEASURED final URL. The Places websiteUri is the owner's
    # stale profile entry; 9 of 10 live http:// leads actually served HTTPS.
    final = (audit or {}).get("final_url") or lead.get("final_url")

    # ---- no HTTPS: rare, so it is a loud signal ------------------------------
    if final and final.lower().startswith("http://"):
        out.append(_p(
            "NO_SSL", 95,
            "Site is not secured (no HTTPS)",
            "The site loads over plain http://. Chrome shows a 'Not secure' warning in the "
            "address bar. Only about 6% of small-business sites still have this problem.",
            "A visible browser warning on a medical or financial site costs trust before "
            "the page even loads. Fast to fix, immediately visible to the owner.",
            "SSL + secure migration", "$300-$800"))

    if not audit:
        return sorted(out, key=lambda p: -p["severity"])

    perf, seo = audit.get("performance"), audit.get("seo")
    a11y, bp = audit.get("accessibility"), audit.get("best_practices")
    lcp = audit.get("lcp_ms")

    # ---- performance ---------------------------------------------------------
    if perf is not None and perf < 90:
        sev = 90 if perf < 40 else 75 if perf < 50 else 55 if perf < 70 else 35
        out.append(_p(
            "SLOW_MOBILE", sev,
            f"Mobile performance {perf}/100 ({band(perf)})",
            f"Google Lighthouse scores this site {perf} out of 100 on mobile"
            + (f", with a largest-contentful-paint of {lcp/1000:.1f}s" if lcp else "")
            + ". Google's own threshold for 'good' is 90.",
            "Most of their customers arrive on a phone. Slow pages lose those visitors "
            "before the page renders, and raise the cost of every paid click. "
            "Sold on conversion and ad cost - not on ranking.",
            "Core Web Vitals / speed remediation", "$750-$2,000"))

    if lcp and lcp > 4000:
        out.append(_p(
            "SLOW_LCP", 70,
            f"Main content takes {lcp/1000:.1f}s to appear",
            f"Largest Contentful Paint is {lcp/1000:.1f} seconds. Google considers "
            f"anything over 2.5s to need improvement and over 4.0s to be poor.",
            "This is the number the owner can feel themselves - open it on your phone "
            "in front of them and count the seconds out loud.",
            "Image/asset optimization", "$500-$1,500"))

    # ---- SEO -----------------------------------------------------------------
    if seo is not None and seo < 90:
        out.append(_p(
            "WEAK_SEO", 80 if seo < 60 else 50,
            f"Technical SEO {seo}/100 ({band(seo)})",
            f"Lighthouse SEO audit scores {seo}/100 - missing meta descriptions, "
            f"link text, crawlability or structured data.",
            "They are invisible to the searches they should own. This is concrete and "
            "checkable, unlike vague 'SEO package' pitches.",
            "Technical SEO remediation", "$800-$2,500"))

    # ---- accessibility: strongest angle for medical/dental/legal -------------
    if a11y is not None and a11y < 90:
        vertical = (lead.get("vertical") or "").lower()
        exposed = any(k in vertical for k in
                      ("dent", "med", "spa", "derm", "law", "clinic", "vet", "financial", "cpa"))
        out.append(_p(
            "ACCESSIBILITY", 85 if exposed else 45,
            f"Accessibility {a11y}/100 ({band(a11y)})",
            f"Lighthouse accessibility audit scores {a11y}/100 - contrast, labels, "
            f"alt text or keyboard navigation issues.",
            ("Healthcare and professional-services sites are the most common targets of "
             "web accessibility demand letters. Frame as risk reduction and reaching "
             "older or impaired patients - never give legal advice."
             if exposed else
             "Excludes customers using assistive tech and is a straightforward fix."),
            "Accessibility remediation (WCAG)", "$1,000-$3,000"))

    if bp is not None and bp < 90:
        out.append(_p(
            "BEST_PRACTICES", 30,
            f"Best practices {bp}/100 ({band(bp)})",
            f"Lighthouse flags {bp}/100 - deprecated APIs, console errors, "
            f"insecure requests or missing source maps.",
            "Low-severity on its own. Use as supporting evidence that the site is "
            "unmaintained, not as the lead argument.",
            "Code health cleanup", "$400-$1,200"))

    return sorted(out, key=lambda p: -p["severity"])

def headline_pain(pains: list[dict]) -> dict | None:
    return pains[0] if pains else None

def scores_worst_to_best(audit: dict | None) -> list[tuple]:
    """Lighthouse categories ordered worst first, for the report column."""
    if not audit:
        return []
    pairs = [("performance", audit.get("performance")), ("SEO", audit.get("seo")),
             ("accessibility", audit.get("accessibility")),
             ("best practices", audit.get("best_practices"))]
    return sorted([(k, v) for k, v in pairs if v is not None], key=lambda kv: kv[1])
