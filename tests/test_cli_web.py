import json
import re

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from opsdesk.cli import app
from opsdesk.web.app import create_app

runner = CliRunner()


def test_cli_end_to_end(paths):
    assert runner.invoke(app, ["--version"]).output.startswith("OpsDesk ")
    r = runner.invoke(app, ["init", "--non-interactive", "--business", "Acme", "--naics", "541511,541519", "--state", "ga"])
    assert r.exit_code == 0, r.output
    assert runner.invoke(app, ["demo"]).exit_code == 0
    leads = json.loads(runner.invoke(app, ["leads", "list", "--json"]).output)
    key = leads[0]["wb_key"]
    assert runner.invoke(app, ["follow", key, "+2d", "call"]).exit_code == 0
    assert runner.invoke(app, ["follow", key, "whenever"]).exit_code == 1
    assert runner.invoke(app, ["status", key, "nope"]).exit_code == 1
    assert runner.invoke(app, ["status", key, "contacted"]).exit_code == 0
    assert runner.invoke(app, ["note", key, "left voicemail"]).exit_code == 0
    today = json.loads(runner.invoke(app, ["today", "--json"]).output)
    assert set(today) == {"overdue", "today", "upcoming"}
    out = runner.invoke(app, ["export"])
    assert out.exit_code == 0 and "Workbook:" in out.output
    assert runner.invoke(app, ["doctor"]).exit_code == 0
    assert runner.invoke(app, ["backup"]).exit_code == 0
    assert runner.invoke(app, ["jobs", "template"]).output.startswith("title:")


def test_spend_needs_confirmation_when_not_interactive(paths, monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "k")
    r = runner.invoke(app, ["leads", "find", "dentists", "in", "Austin", "TX"])
    assert r.exit_code == 2 and "--yes" in r.output


def _token(html):
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def test_dashboard_pages_and_guards(paths):
    runner.invoke(app, ["demo"])
    client = TestClient(create_app(paths))
    for url in ("/", "/area/lead", "/area/bid", "/area/job", "/resume", "/activity", "/settings"):
        res = client.get(url)
        assert res.status_code == 200, url
        assert "Content-Security-Policy" in res.headers
    assert client.get("/", headers={"host": "evil.example"}).status_code == 403
    assert client.get("/area/nope").status_code == 404
    page = client.get("/area/lead").text
    key = re.search(r'href="/item/(lead:[^"]+)"', page).group(1)
    assert client.post(f"/item/{key}/update", data={"status": "contacted"}).status_code == 403
    token = _token(page)
    res = client.post(f"/item/{key}/update", data={"csrf": token, "status": "meeting", "priority": "high",
                                                   "followup_date": "2026-11-05", "followup_note": "demo", "contacted": "on"},
                      follow_redirects=False)
    assert res.status_code == 303
    detail = client.get(f"/item/{key}").text
    assert "meeting" in detail and "2026-11-05" in detail
    res = client.post(f"/item/{key}/update", data={"csrf": token, "status": "bogus"}, follow_redirects=False)
    assert "err=" in res.headers["location"]
    assert client.post(f"/item/{key}/quick", data={"csrf": token, "action": "note", "note": "hi"}, follow_redirects=False).status_code == 303
    assert client.post("/leads/find", data={"csrf": token, "query": "plumbers in Reno NV", "mode": "demo"}, follow_redirects=False).status_code == 303
    res = client.post("/jobs/add", data={"csrf": token, "capture_text": "title: QA\ncompany: Co\nrequired:\n- Python\n---\nx"}, follow_redirects=False)
    assert res.headers["location"].startswith("/item/job:")
    assert client.post("/export", data={"csrf": token}, follow_redirects=False).status_code == 303


def test_cli_secondary_commands(paths, tmp_path):
    runner.invoke(app, ["demo"])
    job = json.loads(runner.invoke(app, ["jobs", "list", "--json"]).output)[0]["wb_key"]
    lead = json.loads(runner.invoke(app, ["leads", "list", "--json"]).output)[0]["wb_key"]
    for args in (["resume", "list"], ["resume", "draft", job], ["jobs", "assess", job], ["leads", "budget"],
                 ["keys", "list"], ["activity"], ["where"], ["statuses"], ["show", lead], ["show", lead, "--json"],
                 ["snooze", lead, "5"], ["done", lead], ["contacted", lead], ["priority", lead, "high"],
                 ["bids", "rank"], ["bids", "list"], ["bids", "report", "--out", str(tmp_path / "r.md")],
                 ["leads", "draft", lead], ["leads", "list", "--open"], ["jobs", "list"], ["import-edits"]):
        res = runner.invoke(app, args)
        assert res.exit_code == 0, (args, res.output)
    assert runner.invoke(app, ["priority", lead, "urgent"]).exit_code == 1
    assert runner.invoke(app, ["export", "--area", "nope"]).exit_code == 1
    capture = tmp_path / "job.md"
    capture.write_text("title: Analyst\ncompany: Gov Co\nrequired:\n- Excel\n---\ntext\n")
    res = runner.invoke(app, ["jobs", "add", str(capture)])
    assert res.exit_code == 0 and "Assessment" in res.output
    key = json.loads(runner.invoke(app, ["jobs", "list", "--json"]).output)[0]["wb_key"]
    res = runner.invoke(app, ["jobs", "applied", key, "--note", "site"])
    assert res.exit_code == 0 and "Receipt" in res.output
    bad = tmp_path / "bad.md"
    bad.write_text("no keys here")
    assert runner.invoke(app, ["jobs", "add", str(bad)]).exit_code == 1
    assert runner.invoke(app, ["leads", "find", "plumbers", "in", "Reno", "NV", "--demo", "--json"]).exit_code == 0
    assert runner.invoke(app, ["bids", "fetch"]).exit_code == 2  # not confirmed, not interactive


def test_dashboard_item_pages_for_each_area(paths):
    runner.invoke(app, ["demo"])
    client = TestClient(create_app(paths))
    page = client.get("/area/job").text
    key = re.search(r'href="/item/(job:[^"]+)"', page).group(1)
    assert "Alignment" in client.get(f"/item/{key}").text
    token = _token(page)
    res = client.post(f"/jobs/applied/{key}", data={"csrf": token, "note": "x"}, follow_redirects=False)
    assert res.status_code == 303
    for action in ("done", "snooze", "tomorrow"):
        assert client.post(f"/item/{key}/quick", data={"csrf": token, "action": action}, follow_redirects=False).status_code == 303
    assert client.get("/item/lead:missing").status_code == 404
    assert client.get("/area/lead?q=works&status=new").status_code == 200
