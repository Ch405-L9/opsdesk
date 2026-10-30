import pytest
import yaml

from opsdesk.jobs import capture, evidence, service
from opsdesk.jobs.assess import assess, resume_bullets
from opsdesk.profile import BusinessProfile, SalaryTargets
from opsdesk.workbench import get_item, workbench

CAPTURE = """title: Web Developer
company: Example Co
url: https://WWW.Jobs.Example.com/123?utm_source=x#apply
location: Remote, US
arrangement: remote
employment: contract
salary_min: 50k
salary_max: 55,000
closes: 2026-12-01
required:
- Python
- JS
- Go
preferred: AWS, Docker
---
We need a developer.
"""


def _evidence(paths, items):
    evidence.evidence_file(paths).write_text(yaml.safe_dump({"items": items}), encoding="utf-8")


def test_capture_parsing_and_cleaning():
    job = capture.parse(CAPTURE)
    assert job["url"] == "https://www.jobs.example.com/123"
    assert (job["salary_min"], job["salary_max"]) == (50000, 55000)
    assert job["required"] == ["Python", "JS", "Go"] and job["preferred"] == ["AWS", "Docker"]
    assert job["description"] == "We need a developer." and len(job["snapshot_sha256"]) == 64
    assert capture.job_key(job) == capture.job_key(capture.parse(CAPTURE))


@pytest.mark.parametrize("bad", ["company: X", "title: X\ncompany: Y\narrangement: moon", "title: X\ncompany: Y\nurl: ftp://x",
                                 "title: X\ncompany: Y\ncloses: soon", "title X"])
def test_capture_errors(bad):
    with pytest.raises(capture.CaptureError):
        capture.parse(bad)


def test_evidence_rejects_contact_data_and_duplicates(paths):
    _evidence(paths, [{"id": "EV-1", "kind": "skill", "title": "Python", "text": "Email me at someone@mail.example"}])
    with pytest.raises(ValueError):
        evidence.load(paths)
    item = {"id": "EV-1", "kind": "skill", "title": "Python", "text": "Builds things"}
    _evidence(paths, [item, item])
    with pytest.raises(ValueError, match="duplicate"):
        evidence.load(paths)


def test_assessment_tiers_gaps_salary_and_bullets(paths):
    _evidence(paths, [
        {"id": "EV-1", "kind": "skill", "title": "Python", "text": "Ships Python tools.", "technologies": ["Python"]},
        {"id": "EV-2", "kind": "project", "title": "Site", "text": "Rebuilt a site in JavaScript.", "technologies": ["JavaScript"]},
    ])
    items = evidence.load(paths)
    job = capture.parse(CAPTURE)
    result = assess(job, items, BusinessProfile(salary_targets=SalaryTargets(minimum=60000), work_arrangements=["onsite"]))
    assert result["technology_alignment"] == round(100 * (1.0 + 0.7) / 3)
    assert result["gaps"] == ["Go"] and result["salary"].startswith("below your minimum")
    assert any("remote" in b for b in result["blockers"]) and "Not a prediction" in result["disclaimer"]
    bullets = resume_bullets(job, items)
    assert [b["text"] for b in bullets] == ["Ships Python tools.", "Rebuilt a site in JavaScript."]


def test_add_assess_and_receipt(paths):
    evidence.init_file(paths)
    key, outcome = service.add(paths, CAPTURE)
    assert outcome == "inserted" and service.add(paths, CAPTURE)[1] == "unchanged"
    service.run_assessment(paths, key)
    receipt = service.record_applied(paths, key, "applied on site")
    assert receipt.exists() and "We need a developer." in receipt.read_text()
    with workbench(paths) as conn:
        item = get_item(conn, key)
        app_row = conn.execute("SELECT status FROM application WHERE job_key=?", (key,)).fetchone()
    assert item["status"] == "applied_manually" and app_row["status"] == "applied_manually"
