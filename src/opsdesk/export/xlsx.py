"""Business-formatted XLSX export with a safe round trip.

Layout per sheet: A = hidden wb_key, B = name (tool), C..I = YOUR columns (yellow header),
then tool columns (navy header). Re-exporting first imports your edits; a cell is applied only
if you changed it since the last export, so a stale file can never undo newer changes.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from opsdesk import __version__, timeutil
from opsdesk.workbench import get_item, list_items, log
from opsdesk.workflow import (
    CLOSED,
    PRIORITIES,
    STATUSES,
    WorkflowError,
    add_note,
    set_fields,
    today_view,
)

CHECK, UNCHECK = "☑", "☐"
USER_COLS: list[tuple[str, str, int]] = [
    ("Status", "status", 16), ("Priority", "priority", 10), ("Done", "done", 7), ("Contacted", "contacted", 10),
    ("Follow-up Date", "followup_date", 14), ("Follow-up Note", "followup_note", 32), ("Notes", "notes", 50),
]
NAME_COL: dict[str, tuple[str, str, int]] = {
    "lead": ("Business", "name", 30), "bid": ("Buyer (sub-agency)", "sub_agency", 34), "job": ("Job title", "title", 32),
}
TOOL_COLS: dict[str, list[tuple[str, str, int, str]]] = {
    "lead": [("Phone", "phone", 16, "text"), ("Website", "website", 32, "url"), ("Address", "address", 36, "text"),
             ("Vertical", "vertical", 16, "text"), ("Rating", "rating", 8, "0.0"), ("Reviews", "review_count", 9, "0"),
             ("Lead score", "priority_score", 10, "0"), ("Need", "need", 7, "0"), ("Ability", "ability", 8, "0"),
             ("Fit", "fit", 6, "0"), ("Reach", "reach", 7, "0"), ("Disqualified", "disqualified", 18, "text")],
    "bid": [("Incumbent", "recipient", 30, "text"), ("Agency", "agency", 28, "text"), ("Amount", "amount", 14, "$#,##0"),
            ("NAICS", "naics", 9, "text"), ("Start", "start", 12, "date"), ("End", "end", 12, "date"),
            ("Lane", "lane", 16, "text"), ("Fit", "fit", 6, "0"), ("Why", "reasons", 50, "text"),
            ("Award page", "url", 30, "url")],
    "job": [("Company", "company", 24, "text"), ("Posting", "url", 32, "url"), ("Location", "location", 20, "text"),
            ("Arrangement", "arrangement", 12, "text"), ("Employment", "employment", 12, "text"),
            ("Salary min", "salary_min", 12, "$#,##0"), ("Salary max", "salary_max", 12, "$#,##0"),
            ("Closes", "closes", 12, "date"), ("Tech alignment", "tech", 13, "0"), ("Gaps", "gaps", 30, "text"),
            ("Blockers", "blockers", 30, "text")],
}
SHEETS = {"lead": "Leads", "bid": "Bids", "job": "Jobs"}
NAVY, WHITE, YELLOW = "1F3864", "FFFFFF", "FFF2CC"
THIN = Side(style="thin", color="D9D9D9")


class ExportLocked(RuntimeError):
    pass


def _lock_files(path: Path) -> list[Path]:
    return [p for p in (path.parent / f"~${path.name}", path.parent / f".~lock.{path.name}#") if p.exists()]


def _safe(cell: Any, value: Any) -> None:
    """Write a value; strings that look like formulas are stored as plain text (formula-injection guard)."""
    if isinstance(value, str):
        cell.value = value
        if value[:1] in ("=", "+", "-", "@", "\t", "\r"):
            cell.data_type = "s"
    else:
        cell.value = value


def _tool_value(item: dict[str, Any], field: str) -> Any:
    if field == "priority_score":
        return item.get("score")
    if field == "tech":
        return (item.get("assessment") or {}).get("technology_alignment")
    if field in {"gaps", "blockers"}:
        return ", ".join((item.get("assessment") or {}).get(field, []))
    if field == "reasons":
        return "; ".join(item.get("reasons", []))
    return item.get(field)


def _user_value(item: dict[str, Any], field: str) -> Any:
    if field in {"done", "contacted"}:
        return CHECK if item[field] else UNCHECK
    if field == "followup_date":
        return timeutil.parse_date(item.get("followup_date"))
    return item.get(field) or ""


def _norm_user(field: str, value: Any) -> Any:
    if field in {"done", "contacted"}:
        if isinstance(value, bool):
            return 1 if value else 0
        return 1 if str(value or "").strip().lower() in {"☑", "✓", "✔", "x", "true", "yes", "y", "1"} else 0
    if field == "followup_date":
        parsed = timeutil.parse_date(value)
        return parsed.isoformat() if parsed else None
    if value is None:
        return ""
    return str(value).strip() if field in {"status", "priority"} else str(value)


def _lists_sheet(wb: Workbook) -> Worksheet:
    ws = wb.create_sheet("_lists")
    columns = [("lead_status", STATUSES["lead"]), ("bid_status", STATUSES["bid"]), ("job_status", STATUSES["job"]),
               ("priority", PRIORITIES), ("check", [UNCHECK, CHECK])]
    for c, (title, values) in enumerate(columns, start=1):
        ws.cell(row=1, column=c, value=title)
        for r, v in enumerate(values, start=2):
            ws.cell(row=r, column=c, value=v)
    ws.sheet_state = "hidden"
    return ws


def _list_ref(col: int, n: int) -> str:
    letter = get_column_letter(col)
    return f"=_lists!${letter}$2:${letter}${n + 1}"


def _area_sheet(wb: Workbook, area: str, items: list[dict[str, Any]]) -> None:
    ws = wb.create_sheet(SHEETS[area])
    headers: list[tuple[str, str, int, str, str]] = [("wb_key", "wb_key", 4, "key", "text")]
    name = NAME_COL[area]
    headers.append((name[0], name[1], name[2], "tool", "text"))
    headers += [(t, f, w, "user", "user") for t, f, w in USER_COLS]
    headers += [(t, f, w, "tool", fmt) for t, f, w, fmt in TOOL_COLS[area]]
    for c, (title, _, width, owner, _) in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=c, value=title)
        cell.font = Font(bold=True, color="000000" if owner == "user" else WHITE)
        cell.fill = PatternFill("solid", fgColor=YELLOW if owner == "user" else NAVY)
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        cell.border = Border(bottom=THIN)
        ws.column_dimensions[get_column_letter(c)].width = width
    ws.row_dimensions[1].height = 30
    ws.column_dimensions["A"].hidden = True
    for r, item in enumerate(items, start=2):
        for c, (_, field, _, owner, fmt) in enumerate(headers, start=1):
            cell = ws.cell(row=r, column=c)
            if owner == "key":
                cell.value = item["wb_key"]
                continue
            value = _user_value(item, field) if owner == "user" else _tool_value(item, field)
            if fmt == "date":
                value = timeutil.parse_date(value)
            _safe(cell, value)
            cell.border = Border(bottom=THIN)
            cell.alignment = Alignment(vertical="top", wrap_text=field in {"notes", "followup_note", "reasons", "address"})
            if fmt == "url" and value:
                cell.hyperlink = str(value)
                cell.style = "Hyperlink"
            if field == name[1] and (item.get("website") or item.get("url")):
                cell.hyperlink = str(item.get("website") or item.get("url"))
                cell.font = Font(color="0563C1", underline="single", bold=True)
            elif field == name[1]:
                cell.font = Font(bold=True)
            if isinstance(value, dt.date) or field == "followup_date":
                cell.number_format = "yyyy-mm-dd"
            elif fmt not in {"text", "url", "user", "date"}:
                cell.number_format = fmt
            if field in {"done", "contacted"}:
                cell.alignment = Alignment(horizontal="center", vertical="top")
                cell.font = Font(size=14)
    last = max(len(items) + 1, 2)
    end_row = max(last, 200)
    col_of = {f: i for i, (_, f, _, _, _) in enumerate(headers, start=1)}
    letter = {f: get_column_letter(i) for f, i in col_of.items()}
    status_list = {"lead": 1, "bid": 2, "job": 3}[area]
    validations = [
        ("status", _list_ref(status_list, len(STATUSES[area])), "Pick a status from the list."),
        ("priority", _list_ref(4, len(PRIORITIES)), "high, normal or low"),
        ("done", _list_ref(5, 2), "☐ or ☑"),
        ("contacted", _list_ref(5, 2), "☐ or ☑"),
    ]
    for field, ref, hint in validations:
        dv = DataValidation(type="list", formula1=ref, allow_blank=True, showErrorMessage=True,
                            errorTitle="Invalid value", error=hint, promptTitle=field.title(), prompt=hint)
        dv.add(f"{letter[field]}2:{letter[field]}{end_row}")
        ws.add_data_validation(dv)
    dv_date = DataValidation(type="date", operator="greaterThan", formula1="DATE(2000,1,1)", allow_blank=True,
                             showErrorMessage=True, error="Enter a date like 2026-11-03")
    dv_date.add(f"{letter['followup_date']}2:{letter['followup_date']}{end_row}")
    ws.add_data_validation(dv_date)
    rng = f"A2:{get_column_letter(len(headers))}{end_row}"
    fd, dn, st = letter["followup_date"], letter["done"], letter["status"]
    closed = ",".join(f'${st}2="{s}"' for s in sorted(CLOSED & set(STATUSES[area])))
    ws.conditional_formatting.add(rng, FormulaRule(formula=[f'AND(${fd}2<>"",${fd}2<TODAY(),${dn}2<>"{CHECK}")'],
                                                   fill=PatternFill("solid", fgColor="F8CBAD"), stopIfTrue=True))
    ws.conditional_formatting.add(rng, FormulaRule(formula=[f'AND(${fd}2=TODAY(),${dn}2<>"{CHECK}")'],
                                                   fill=PatternFill("solid", fgColor="FFE699"), stopIfTrue=True))
    ws.conditional_formatting.add(rng, FormulaRule(formula=[f'AND(${fd}2>TODAY(),${fd}2<=TODAY()+3,${dn}2<>"{CHECK}")'],
                                                   fill=PatternFill("solid", fgColor="FFF9DB"), stopIfTrue=True))
    if closed:
        ws.conditional_formatting.add(rng, FormulaRule(formula=[f"OR({closed})"], font=Font(color="808080")))
    ws.conditional_formatting.add(f"{dn}2:{dn}{end_row}", FormulaRule(formula=[f'${dn}2="{CHECK}"'],
                                                                     fill=PatternFill("solid", fgColor="C6EFCE")))
    ws.conditional_formatting.add(rng, FormulaRule(formula=["MOD(ROW(),2)=0"], fill=PatternFill("solid", fgColor="F7F9FC")))
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{last}"
    ws.sheet_view.zoomScale = 110


def _today_sheet(wb: Workbook, conn: sqlite3.Connection, tz: str | None) -> None:
    ws = wb.active
    ws.title = "Today"
    ws["A1"] = "OpsDesk: today's follow-ups"
    ws["A1"].font = Font(bold=True, size=16, color=NAVY)
    ws["A2"] = f"Generated {timeutil.now_iso(tz)} · edit status, dates and notes on the Leads, Bids and Jobs sheets"
    ws["A2"].font = Font(italic=True, color="666666")
    headers = ["When", "Due", "Area", "Item", "Follow-up note", "Status", "Priority"]
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=c, value=h)
        cell.font, cell.fill = Font(bold=True, color=WHITE), PatternFill("solid", fgColor=NAVY)
    fills = {"overdue": "F8CBAD", "today": "FFE699", "upcoming": "FFFFFF"}
    r = 5
    from opsdesk.workbench import label

    for bucket, rows in today_view(conn, tz).items():
        for item in rows:
            values = [bucket.title(), timeutil.parse_date(item["followup_date"]), item["wb_key"].split(":")[0],
                      label(item), item.get("followup_note") or "", item["status"], item["priority"]]
            for c, v in enumerate(values, start=1):
                cell = ws.cell(row=r, column=c)
                _safe(cell, v)
                cell.fill = PatternFill("solid", fgColor=fills[bucket])
                if c == 2:
                    cell.number_format = "yyyy-mm-dd"
            r += 1
    if r == 5:
        ws.cell(row=5, column=1, value="Nothing due in the next 7 days.")
    for c, w in enumerate([10, 12, 8, 44, 40, 16, 10], start=1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = "A5"


def _latest_export(conn: sqlite3.Connection, path: Path) -> int | None:
    row = conn.execute("SELECT id FROM export WHERE path=? ORDER BY id DESC LIMIT 1", (str(path.resolve()),)).fetchone()
    return int(row["id"]) if row else None


def import_edits(conn: sqlite3.Connection, path: Path, tz: str | None = None) -> dict[str, Any]:
    """Apply only the cells you changed since the last export of this file."""
    path = Path(path)
    if _lock_files(path):
        raise ExportLocked(f"{path.name} looks open in a spreadsheet app. Save and close it first.")
    export_id = _latest_export(conn, path)
    report: dict[str, Any] = {"applied": 0, "rows": 0, "skipped_unknown": 0, "errors": []}
    if export_id is None or not path.exists():
        return report
    snap: dict[tuple[str, str], Any] = {
        (r["wb_key"], r["column_name"]): json.loads(r["value_json"]) for r in
        conn.execute("SELECT wb_key,column_name,value_json FROM export_cell WHERE export_id=?", (export_id,))
    }
    wb = load_workbook(path)
    for sheet in SHEETS.values():
        if sheet not in wb.sheetnames:
            continue
        ws = wb[sheet]
        header = {str(ws.cell(row=1, column=c).value): c for c in range(1, ws.max_column + 1)}
        for r in range(2, ws.max_row + 1):
            key = ws.cell(row=r, column=1).value
            if not key:
                continue
            key = str(key)
            if get_item(conn, key) is None:
                report["skipped_unknown"] += 1
                continue
            report["rows"] += 1
            changes: dict[str, Any] = {}
            for title, field, _ in USER_COLS:
                if title not in header:
                    continue
                new = _norm_user(field, ws.cell(row=r, column=header[title]).value)
                old = snap.get((key, field))
                if (key, field) in snap and new != old:
                    changes[field] = new
            if not changes:
                continue
            try:
                notes = changes.pop("notes", None)
                if changes:
                    set_fields(conn, key, "xlsx", **changes)
                if notes is not None:
                    old_notes = snap.get((key, "notes")) or ""
                    if old_notes and notes.startswith(old_notes) and notes[len(old_notes):].strip():
                        add_note(conn, key, notes[len(old_notes):].strip(), actor="xlsx", tz=tz)
                    else:
                        set_fields(conn, key, "xlsx", notes=notes)
                report["applied"] += 1
            except (WorkflowError, KeyError) as exc:
                report["errors"].append(f"{sheet} row {r}: {exc}")
    log(conn, "xlsx.import", None, {"path": str(path), **{k: v for k, v in report.items() if k != "errors"}}, "xlsx")
    return report


def export(conn: sqlite3.Connection, path: Path, areas: list[str] | None = None, tz: str | None = None) -> dict[str, Any]:
    path = Path(path).resolve()
    areas = areas or ["lead", "bid", "job"]
    if _lock_files(path):
        raise ExportLocked(f"{path.name} looks open in a spreadsheet app. Save and close it first.")
    imported = import_edits(conn, path, tz) if path.exists() else {"applied": 0}
    wb = Workbook()
    _today_sheet(wb, conn, tz)
    items_by_area = {area: list_items(conn, area, limit=10000) for area in areas}
    for area in areas:
        _area_sheet(wb, area, items_by_area[area])
    _lists_sheet(wb)
    meta = wb.create_sheet("_meta")
    meta["A1"], meta["B1"] = "generated_by", f"OpsDesk {__version__}"
    meta["A2"], meta["B2"] = "generated_at", timeutil.now_iso(tz)
    meta.sheet_state = "hidden"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_suffix(".prev.xlsx"))
    tmp = path.with_suffix(".tmp.xlsx")
    wb.save(tmp)
    tmp.replace(path)
    cur = conn.execute("INSERT INTO export(path,exported_at,areas_json) VALUES(?,?,?)",
                       (str(path), timeutil.now_iso(tz), json.dumps(areas)))
    export_id = cur.lastrowid
    rows = []
    for area in areas:
        for item in items_by_area[area]:
            for _, field, _ in USER_COLS:
                value = _user_value(item, field)
                rows.append((export_id, item["wb_key"], field, json.dumps(_norm_user(field, value))))
    conn.executemany("INSERT INTO export_cell(export_id,wb_key,column_name,value_json) VALUES(?,?,?,?)", rows)
    counts = {area: len(items_by_area[area]) for area in areas}
    log(conn, "xlsx.export", None, {"path": str(path), "counts": counts, "imported": imported.get("applied", 0)})
    return {"path": str(path), "counts": counts, "imported_edits": imported.get("applied", 0)}
