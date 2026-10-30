"""Local dashboard. Bound to 127.0.0.1; Host-header check; CSRF token on every POST."""

from __future__ import annotations

import secrets as pysecrets
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from opsdesk import __version__, secrets, timeutil
from opsdesk.paths import AppPaths
from opsdesk.profile import load_profile
from opsdesk.workbench import get_item, label, list_items, workbench
from opsdesk.workflow import (
    CLOSED,
    PRIORITIES,
    STATUSES,
    WorkflowError,
    add_note,
    counts,
    follow,
    mark_done,
    set_fields,
    snooze,
    today_view,
)

HERE = Path(__file__).parent
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "testserver"}
AREA_TITLES = {"lead": "Leads", "bid": "Bids", "job": "Jobs"}


def create_app(paths: AppPaths) -> FastAPI:
    app = FastAPI(title="OpsDesk", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")
    token = pysecrets.token_urlsafe(32)
    templates.env.globals.update(csrf=token, version=__version__, label=label, statuses=STATUSES,
                                 priorities=PRIORITIES, closed=CLOSED, area_titles=AREA_TITLES)

    @app.middleware("http")
    async def guard(request: Request, call_next: Any) -> Response:
        host = (request.headers.get("host") or "").split(":")[0]
        if host not in ALLOWED_HOSTS:
            return Response("Forbidden host", status_code=403)
        response: Response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:"
        return response

    def check(csrf: str) -> None:
        if not pysecrets.compare_digest(csrf or "", token):
            raise HTTPException(403, "Missing or invalid form token. Reload the page.")

    def tz() -> str:
        return load_profile(paths.profile_file).timezone

    def back(request: Request, msg: str = "", error: bool = False) -> RedirectResponse:
        ref = request.headers.get("referer") or "/"
        target = ref.split("?")[0]
        if not target.startswith(("http://127.0.0.1", "http://localhost", "http://testserver", "/")):
            target = "/"
        flag = "err" if error else "msg"
        return RedirectResponse(f"{target}?{flag}={quote(msg)}" if msg else target, status_code=303)

    def render(request: Request, name: str, **ctx: Any) -> HTMLResponse:
        ctx.update(request=request, msg=request.query_params.get("msg"), err=request.query_params.get("err"),
                   profile=load_profile(paths.profile_file), today=timeutil.today(tz()).isoformat())
        return templates.TemplateResponse(request, name, ctx)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        with workbench(paths) as conn:
            view = today_view(conn, tz())
            tallies = counts(conn)
        return render(request, "today.html", view=view, tallies=tallies)

    @app.get("/area/{area}", response_class=HTMLResponse)
    def area_page(request: Request, area: str, status: str | None = None, q: str = "") -> HTMLResponse:
        if area not in AREA_TITLES:
            raise HTTPException(404)
        with workbench(paths) as conn:
            items = list_items(conn, area, status=status or None, limit=2000)
        if q:
            needle = q.lower()
            items = [i for i in items if needle in label(i).lower()]
        if area == "lead":
            items.sort(key=lambda i: -(i.get("score") or 0))
        elif area == "bid":
            items.sort(key=lambda i: -(i.get("fit") or 0))
        board = {s: [i for i in items if i["status"] == s] for s in STATUSES[area]}
        return render(request, "area.html", area=area, items=items, board=board, status=status, q=q)

    @app.get("/item/{wb_key:path}", response_class=HTMLResponse)
    def item_page(request: Request, wb_key: str) -> HTMLResponse:
        with workbench(paths) as conn:
            item = get_item(conn, wb_key)
            notes = conn.execute("SELECT body, created_at, created_by FROM note WHERE wb_key=? ORDER BY id DESC", (wb_key,)).fetchall()
            history = conn.execute("SELECT action, created_at, actor FROM activity WHERE wb_key=? ORDER BY id DESC LIMIT 30", (wb_key,)).fetchall()
        if item is None:
            raise HTTPException(404)
        area = wb_key.split(":")[0]
        return render(request, "item.html", item=item, area=area, notes=notes, history=history)

    @app.post("/item/{wb_key:path}/update")
    def item_update(request: Request, wb_key: str, status: str = Form(""), priority: str = Form(""),
                    followup_date: str = Form(""), followup_note: str = Form(""),
                    contacted: str = Form(""), done: str = Form(""), csrf: str = Form("")) -> RedirectResponse:
        check(csrf)
        try:
            with workbench(paths) as conn:
                changes: dict[str, Any] = {"contacted": contacted == "on", "done": done == "on"}
                if status:
                    changes["status"] = status
                if priority:
                    changes["priority"] = priority
                changes["followup_date"] = followup_date or None
                changes["followup_note"] = followup_note
                set_fields(conn, wb_key, "dashboard", **changes)
        except (WorkflowError, KeyError) as exc:
            return back(request, str(exc), error=True)
        return back(request, "Saved")

    @app.post("/item/{wb_key:path}/quick")
    def item_quick(request: Request, wb_key: str, action: str = Form(...), note: str = Form(""), csrf: str = Form("")) -> RedirectResponse:
        check(csrf)
        try:
            with workbench(paths) as conn:
                if action == "done":
                    mark_done(conn, wb_key, "dashboard")
                elif action == "snooze":
                    snooze(conn, wb_key, 3, tz(), "dashboard")
                elif action == "tomorrow":
                    follow(conn, wb_key, timeutil.parse_when("tomorrow", tz()), note, "dashboard")
                elif action == "note":
                    add_note(conn, wb_key, note, "dashboard", tz())
                else:
                    raise WorkflowError("Unknown action")
        except (WorkflowError, KeyError) as exc:
            return back(request, str(exc), error=True)
        return back(request, {"done": "Marked done", "snooze": "Snoozed 3 days", "tomorrow": "Follow-up set for tomorrow",
                              "note": "Note added"}[action])

    @app.post("/leads/find")
    def leads_find(request: Request, query: str = Form(...), mode: str = Form("demo"),
                   confirm_spend: str = Form(""), csrf: str = Form("")) -> RedirectResponse:
        check(csrf)
        from opsdesk.leads import service

        try:
            plan = service.plan_find(paths, query)
            if mode == "api" and plan["cost_calls"] and confirm_spend.strip().lower() != "spend":
                return back(request, "Type 'spend' to confirm using 1 Google Places call.", error=True)
            result = service.find(paths, query, demo=mode == "demo", confirmed=True)
        except (ValueError, RuntimeError, PermissionError) as exc:
            return back(request, str(exc), error=True)
        return back(request, f"{len(result.rows)} leads from {result.source}")

    @app.post("/jobs/add")
    def jobs_add(request: Request, capture_text: str = Form(...), csrf: str = Form("")) -> RedirectResponse:
        check(csrf)
        from opsdesk.jobs import service
        from opsdesk.jobs.capture import CaptureError

        try:
            key, _ = service.add(paths, capture_text, origin="dashboard")
            service.run_assessment(paths, key)
        except (CaptureError, ValueError) as exc:
            return back(request, str(exc), error=True)
        return RedirectResponse(f"/item/{key}?msg=Job+saved+and+assessed", status_code=303)

    @app.post("/jobs/applied/{wb_key:path}")
    def jobs_applied(request: Request, wb_key: str, note: str = Form(""), csrf: str = Form("")) -> RedirectResponse:
        check(csrf)
        from opsdesk.jobs import service

        path = service.record_applied(paths, wb_key, note)
        return back(request, f"Recorded. Receipt saved: {path.name}")

    @app.post("/export")
    def export_xlsx(request: Request, csrf: str = Form("")) -> RedirectResponse:
        check(csrf)
        from opsdesk.export.xlsx import ExportLocked, export

        target = paths.data_dir / "exports" / "OpsDesk.xlsx"
        try:
            with workbench(paths) as conn:
                result = export(conn, target, None, tz())
        except ExportLocked as exc:
            return back(request, str(exc), error=True)
        return back(request, f"Workbook saved: {result['path']} ({result['imported_edits']} edited rows imported first)")

    @app.get("/resume", response_class=HTMLResponse)
    def resume(request: Request) -> HTMLResponse:
        from opsdesk.jobs import evidence

        try:
            items, problem = evidence.load(paths), None
        except ValueError as exc:
            items, problem = [], str(exc)
        return render(request, "resume.html", items=items, problem=problem, path=evidence.evidence_file(paths))

    @app.get("/activity", response_class=HTMLResponse)
    def activity(request: Request) -> HTMLResponse:
        with workbench(paths) as conn:
            rows = conn.execute("SELECT created_at, actor, action, wb_key FROM activity ORDER BY id DESC LIMIT 200").fetchall()
        return render(request, "activity.html", rows=rows)

    @app.get("/settings", response_class=HTMLResponse)
    def settings(request: Request) -> HTMLResponse:
        from opsdesk.leads.service import quota_report

        return render(request, "settings.html", keys=secrets.configured(paths), quotas=quota_report(paths), paths=paths)

    return app
