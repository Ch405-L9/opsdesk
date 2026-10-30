"""Assess a captured job against the user's evidence and profile. Never a verdict or an odds estimate."""

from __future__ import annotations

from typing import Any

from opsdesk.jobs.evidence import TIER, EvidenceItem, index, norm
from opsdesk.profile import BusinessProfile


def assess(job: dict[str, Any], evidence: list[EvidenceItem], profile: BusinessProfile) -> dict[str, Any]:
    idx = index(evidence)
    matches, gaps = [], []
    total = 0.0
    for term in job.get("required", []):
        hits = idx.get(norm(term), [])
        if hits:
            best = hits[0]
            total += TIER[best.kind]
            matches.append({"term": term, "evidence_id": best.id, "kind": best.kind, "weight": TIER[best.kind]})
        else:
            gaps.append(term)
    required = job.get("required", [])
    tech = round(100 * total / len(required)) if required else None
    preferred_hits = [t for t in job.get("preferred", []) if norm(t) in idx]

    salary = "unknown"
    floor = profile.salary_targets.minimum
    top = job.get("salary_max") or job.get("salary_min")
    if floor and top:
        salary = "meets target" if top >= floor else f"below your minimum by ${floor - top:,}"
    elif floor:
        salary = "not stated (ask)"

    arrangement = job.get("arrangement", "unknown")
    arrangement_ok = arrangement == "unknown" or arrangement in profile.work_arrangements
    blockers = []
    clearance = str(job.get("clearance", "")).strip().lower()
    if clearance and clearance not in {"none", "no", "n/a", "unknown"}:
        blockers.append(f"clearance required: {job['clearance']}")
    if not arrangement_ok:
        blockers.append(f"{arrangement} is not in your work arrangements")

    notes = []
    if tech is not None:
        notes.append(f"Technology alignment {tech}/100 from {len(matches)} of {len(required)} required items with evidence.")
    if gaps:
        notes.append("Gaps (do not claim these): " + ", ".join(gaps))
    return {"technology_alignment": tech, "matches": matches, "gaps": gaps, "preferred_hits": preferred_hits,
            "salary": salary, "arrangement_ok": arrangement_ok, "blockers": blockers, "notes": notes,
            "disclaimer": "Decision support only. Not a prediction of getting hired."}


def resume_bullets(job: dict[str, Any], evidence: list[EvidenceItem]) -> list[dict[str, str]]:
    """Every bullet is a verbatim evidence statement with its id. Nothing is invented."""
    by_id = {e.id: e for e in evidence}
    seen: set[str] = set()
    bullets = []
    for match in assess(job, evidence, BusinessProfile())["matches"]:
        if match["evidence_id"] in seen:
            continue
        seen.add(match["evidence_id"])
        item = by_id[match["evidence_id"]]
        bullets.append({"evidence_id": item.id, "for": match["term"], "text": item.text})
    return bullets
