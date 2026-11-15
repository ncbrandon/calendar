"""OpsBoard web server: the API behind the wall screens and the web page."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import shutil
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import db, exporter, holidays, importer, rotation, sampling, weather

STATIC = Path(__file__).resolve().parent / "static"
ADMIN_PASSWORD = os.environ.get("OPSBOARD_PASSWORD", "")
KIOSK_TOKEN = os.environ.get("OPSBOARD_KIOSK_TOKEN", "")
COOKIE = "opsboard_session"
MEDIA_TYPES = {"gif": {".gif", ".webp", ".png", ".jpg", ".jpeg"}, "video": {".mp4", ".webm", ".mov", ".m4v"}}
DOC_TYPES = {".pdf", ".csv", ".xlsx", ".txt", ".docx", ".png", ".jpg", ".jpeg"}
CATEGORIES = ["general", "maintenance", "delivery", "meeting", "inspection", "time off", "reminder"]

app = FastAPI(title="OpsBoard", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


class State:
    version = 1          # bumped on every change so the screens know to reload
    nav_offset = 0       # months away from "this month" that the wall is showing
    nav_at = 0.0
    wake_until = 0.0     # a tap on a dark screen keeps it on until this time
    planned_for = None   # last day the sampling planner ran


def touch() -> None:
    State.version += 1


def today() -> date:
    return date.today()


def is_dark(settings: dict, now: Optional[datetime] = None) -> bool:
    now = now or datetime.now()
    if time.time() < State.wake_until:
        return False
    hhmm = now.strftime("%H:%M")
    working = now.weekday() in (settings.get("work_days") or []) and settings["work_start"] <= hhmm < settings["work_end"]
    return not working


def plan_if_needed(conn, settings: dict) -> None:
    if State.planned_for != today():
        sampling.ensure_tasks(conn, settings, today())
        State.planned_for = today()


def replan(conn, settings: dict) -> None:
    sampling.ensure_tasks(conn, settings, today())
    State.planned_for = today()
    touch()


@app.on_event("startup")
def startup() -> None:
    db.init()
    with db.db() as conn:
        plan_if_needed(conn, db.get_settings(conn))


# --- Sign-in ----------------------------------------------------------------

def _session_value() -> str:
    with db.db() as conn:
        secret = db.get_secret(conn, "session")
    return hmac.new(secret.encode(), ADMIN_PASSWORD.encode(), hashlib.sha256).hexdigest()


@app.middleware("http")
async def auth(request: Request, call_next):
    path = request.url.path
    if not ADMIN_PASSWORD or path.startswith(("/static/", "/login", "/healthz")):
        return await call_next(request)
    expected = _session_value()
    if hmac.compare_digest(request.cookies.get(COOKIE, ""), expected):
        return await call_next(request)
    token = request.query_params.get("token", "")
    if KIOSK_TOKEN and token and hmac.compare_digest(token, KIOSK_TOKEN):
        response = await call_next(request)
        response.set_cookie(COOKIE, expected, max_age=10 * 365 * 86400, httponly=True, samesite="lax")
        return response
    if path.startswith("/api/"):
        return JSONResponse({"detail": "Sign in first"}, status_code=401)
    return RedirectResponse("/login", status_code=303)


LOGIN_PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>OpsBoard sign in</title><link rel=stylesheet href=/static/app.css>
<body class=login><form method=post action=/login class=card><h1>OpsBoard</h1>
<p class=muted>Enter the password to manage the calendar.</p>%s
<input type=password name=password placeholder=Password autofocus required>
<button class=primary>Sign in</button></form>"""


@app.get("/login", response_class=HTMLResponse)
def login_page(error: int = 0):
    return LOGIN_PAGE % ("<p class=error>Wrong password.</p>" if error else "")


@app.post("/login")
def login(password: str = Form(...)):
    if not ADMIN_PASSWORD or not hmac.compare_digest(password, ADMIN_PASSWORD):
        return RedirectResponse("/login?error=1", status_code=303)
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(COOKIE, _session_value(), max_age=30 * 86400, httponly=True, samesite="lax")
    return response


@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return "ok"


# --- Pages ------------------------------------------------------------------

@app.get("/")
def root():
    return RedirectResponse("/admin")


@app.get("/admin")
def admin_page():
    return FileResponse(STATIC / "admin.html", headers={"Cache-Control": "no-store"})


@app.get("/preview")
def preview_page():
    """Both wall screens side by side in one browser window, for trying things from a desk."""
    return FileResponse(STATIC / "preview.html", headers={"Cache-Control": "no-store"})


@app.get("/display")
def display_page():
    return FileResponse(STATIC / "display.html", headers={"Cache-Control": "no-store"})


# --- Live state for the wall screens ---------------------------------------

def state_payload() -> dict:
    with db.db() as conn:
        settings = db.get_settings(conn)
    idle = settings.get("idle_return_minutes", 3) * 60
    if State.nav_offset and time.time() - State.nav_at > idle:
        State.nav_offset = 0
    return {"version": State.version, "nav_offset": State.nav_offset, "dark": is_dark(settings),
            "today": today().isoformat()}


@app.get("/api/state")
def get_state():
    return state_payload()


@app.get("/api/stream")
async def stream(request: Request):
    async def events():
        last, quiet = None, 0
        while not await request.is_disconnected():
            payload = await asyncio.get_event_loop().run_in_executor(None, state_payload)
            if payload != last:
                last, quiet = payload, 0
                yield f"data: {json.dumps(payload)}\n\n"
            else:
                quiet += 1
                if quiet % 15 == 0:
                    yield ": keep-alive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.post("/api/nav")
def set_nav(payload: dict = Body(...)):
    State.nav_offset = max(-600, min(600, int(payload.get("offset", 0))))
    State.nav_at = time.time()
    return state_payload()


@app.post("/api/wake")
def wake():
    with db.db() as conn:
        minutes = db.get_settings(conn).get("wake_minutes", 5)
    State.wake_until = time.time() + minutes * 60
    return state_payload()


# --- Calendar ---------------------------------------------------------------

def employees(conn, include_inactive: bool = False) -> list:
    where = "" if include_inactive else "WHERE active = 1"
    return db.rows(conn.execute(f"SELECT * FROM employees {where} ORDER BY sort, id"))


@app.get("/api/bootstrap")
def bootstrap():
    with db.db() as conn:
        return {"settings": db.get_settings(conn), "employees": employees(conn), "categories": CATEGORIES,
                "frequencies": sampling.FREQUENCY_LABELS, "conditions": weather.LABELS,
                "ai_enabled": importer.ai_enabled(), "password_set": bool(ADMIN_PASSWORD)}


@app.get("/api/month")
def month(ym: str):
    try:
        year, mon = (int(x) for x in ym.split("-"))
        first = date(year, mon, 1)
    except ValueError:
        raise HTTPException(400, "ym must look like 2026-11")
    last = sampling.add_months(first, 1) - timedelta(days=1)
    grid_start = first - timedelta(days=(first.weekday() + 1) % 7)   # back to Sunday
    grid_end = last + timedelta(days=(5 - last.weekday()) % 7)        # forward to Saturday
    with db.db() as conn:
        settings = db.get_settings(conn)
        plan_if_needed(conn, settings)
        hol = holidays.detail(conn, settings, grid_start, grid_end)
        oncall = rotation.oncall_between(conn, settings, grid_start, grid_end)
        samples = sampling.calendar_items(conn, grid_start, grid_end, today())
        events = db.rows(conn.execute(
            "SELECT * FROM events WHERE date <= ? AND COALESCE(end_date, date) >= ? ORDER BY COALESCE(time, ''), id",
            (grid_end.isoformat(), grid_start.isoformat())))
        staff = employees(conn)
    pay_start, payday = settings.get("pay_week_start", 6), settings.get("payday_weekday")
    days, day = [], grid_start
    while day <= grid_end:
        iso = day.isoformat()
        items = [dict(e, type="event") for e in events if e["date"] <= iso <= (e["end_date"] or e["date"])]
        pay = []
        if day.weekday() == pay_start:
            pay.append("start")
        if day.weekday() == (pay_start - 1) % 7:
            pay.append("end")
        if payday is not None and day.weekday() == payday:
            pay.append("payday")
        days.append({"date": iso, "in_month": day.month == mon, "weekday": day.weekday(),
                     "holiday": hol[iso]["name"] if iso in hol else None,
                     "holiday_id": hol[iso]["id"] if iso in hol else None,
                     "pay": pay, "oncall": oncall[iso],
                     "items": samples.get(iso, []) + items})
        day += timedelta(days=1)
    return {"ym": ym, "title": first.strftime("%B %Y"), "today": today().isoformat(), "days": days,
            "employees": staff, "rotation_start_weekday": settings.get("rotation_start_weekday", 3)}


def _event_fields(payload: dict) -> dict:
    title = str(payload.get("title", "")).strip()
    if not title:
        raise HTTPException(400, "An event needs a title")
    try:
        day = date.fromisoformat(str(payload.get("date", "")))
        end = payload.get("end_date") or None
        if end and date.fromisoformat(end) <= day:
            end = None
    except ValueError:
        raise HTTPException(400, "Dates must look like 2026-11-14")
    when = payload.get("time") or None
    if when and not re.fullmatch(r"\d{2}:\d{2}", when):
        raise HTTPException(400, "Time must look like 14:30")
    return {"title": title[:200], "date": day.isoformat(), "end_date": end, "time": when,
            "category": str(payload.get("category") or "general")[:40], "notes": str(payload.get("notes") or "")[:2000],
            "done": 1 if payload.get("done") else 0}


@app.post("/api/events")
def create_event(payload: dict = Body(...)):
    f = _event_fields(payload)
    with db.db() as conn:
        cur = conn.execute(
            "INSERT INTO events (title, date, end_date, time, category, notes, done, source) VALUES (?,?,?,?,?,?,?,?)",
            (f["title"], f["date"], f["end_date"], f["time"], f["category"], f["notes"], f["done"],
             str(payload.get("source") or "web")[:20]))
    touch()
    return {"id": cur.lastrowid}


@app.put("/api/events/{event_id}")
def update_event(event_id: int, payload: dict = Body(...)):
    with db.db() as conn:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "No such event")
        f = _event_fields({**dict(row), **payload})
        conn.execute("UPDATE events SET title=?, date=?, end_date=?, time=?, category=?, notes=?, done=? WHERE id=?",
                     (f["title"], f["date"], f["end_date"], f["time"], f["category"], f["notes"], f["done"], event_id))
    touch()
    return {"ok": True}


@app.delete("/api/events/{event_id}")
def delete_event(event_id: int):
    with db.db() as conn:
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    touch()
    return {"ok": True}


@app.post("/api/oncall")
def set_oncall(payload: dict = Body(...)):
    try:
        day = date.fromisoformat(str(payload.get("date")))
    except ValueError:
        raise HTTPException(400, "Bad date")
    emp = payload.get("employee_id")
    with db.db() as conn:
        try:
            rotation.set_oncall(conn, db.get_settings(conn), day, int(emp) if emp not in (None, "") else None)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
    touch()
    return {"ok": True}


# --- Staff, holidays, settings ---------------------------------------------

@app.get("/api/employees")
def list_employees():
    with db.db() as conn:
        return employees(conn, include_inactive=True)


@app.post("/api/employees")
def save_employee(payload: dict = Body(...)):
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(400, "Name is required")
    values = (name[:40], str(payload.get("color") or "#4f8cc9")[:9], 1 if payload.get("in_rotation") else 0,
              int(payload.get("sort") or 0), 0 if payload.get("active") in (0, False) else 1)
    with db.db() as conn:
        if payload.get("id"):
            conn.execute("UPDATE employees SET name=?, color=?, in_rotation=?, sort=?, active=? WHERE id=?",
                         values + (int(payload["id"]),))
        else:
            conn.execute("INSERT INTO employees (name, color, in_rotation, sort, active) VALUES (?,?,?,?,?)", values)
    touch()
    return {"ok": True}


@app.get("/api/holidays")
def list_holidays(year: int):
    with db.db() as conn:
        settings = db.get_settings(conn)
        every = holidays.detail(conn, settings, date(year, 1, 1), date(year, 12, 31))
        custom = db.rows(conn.execute("SELECT * FROM holidays ORDER BY date"))
    return {"all": [{"date": d, "name": h["name"], "id": h["id"]} for d, h in sorted(every.items())], "custom": custom,
            "federal_names": sorted({n for n in holidays.federal(year).values() if "observed" not in n}),
            "extra_names": holidays.EXTRA_NAMES}


@app.post("/api/holidays")
def add_holiday(payload: dict = Body(...)):
    """One day off, or a run of days (end_date), once or every year on the same dates (yearly)."""
    try:
        day = date.fromisoformat(str(payload.get("date")))
        end = date.fromisoformat(str(payload["end_date"])) if payload.get("end_date") else None
    except ValueError:
        raise HTTPException(400, "Pick the first day of the holiday")
    if end and end <= day:
        end = None
    if end and (end - day).days > 31:
        raise HTTPException(400, "A holiday can run at most a month")
    name = str(payload.get("name") or "").strip() or "Holiday"
    with db.db() as conn:
        conn.execute("INSERT INTO holidays (date, end_date, name, yearly) VALUES (?, ?, ?, ?)",
                     (day.isoformat(), end.isoformat() if end else None, name[:80], 1 if payload.get("yearly") else 0))
    touch()
    return {"ok": True}


@app.delete("/api/holidays/{holiday_id}")
def delete_holiday(holiday_id: int):
    with db.db() as conn:
        conn.execute("DELETE FROM holidays WHERE id = ?", (holiday_id,))
    touch()
    return {"ok": True}


@app.get("/api/weather")
def weather_now():
    """A fresh reading, for the 'Check the weather now' button on the Settings tab."""
    with db.db() as conn:
        settings = db.get_settings(conn)
    return {"weather": weather.current(settings, fresh=True)}


@app.put("/api/settings")
def save_settings(payload: dict = Body(...)):
    if payload.get("station_url"):
        payload["station_url"] = str(payload["station_url"]).strip()[:300]
        if not re.match(r"https?://", payload["station_url"]):
            raise HTTPException(400, "The weather station address must start with http:// or https://")
    for key in ("work_start", "work_end"):
        if key in payload and not re.fullmatch(r"\d{2}:\d{2}", str(payload[key])):
            raise HTTPException(400, f"{key} must look like 07:00")
    with db.db() as conn:
        db.set_settings(conn, payload)
        replan(conn, db.get_settings(conn))
    return {"ok": True}


# --- Sampling ---------------------------------------------------------------

@app.get("/api/requirements")
def list_requirements():
    with db.db() as conn:
        out = db.rows(conn.execute("SELECT * FROM requirements ORDER BY program, name"))
    for r in out:
        r["allowed_months"] = json.loads(r["allowed_months"] or "[]")
    return out


def _insert_requirement(conn, f: dict) -> int:
    keys = list(f)
    cur = conn.execute(f"INSERT INTO requirements ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
                       [f[k] for k in keys])
    return cur.lastrowid


@app.post("/api/requirements")
def save_requirement(payload: dict = Body(...)):
    try:
        f = importer.clean(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    with db.db() as conn:
        if payload.get("id"):
            rid = int(payload["id"])
            conn.execute(f"UPDATE requirements SET {', '.join(k + ' = ?' for k in f)} WHERE id = ?", list(f.values()) + [rid])
            sampling.reset_requirement(conn, rid)
        else:
            rid = _insert_requirement(conn, f)
        replan(conn, db.get_settings(conn))
    return {"id": rid}


@app.post("/api/requirements/bulk")
def save_requirements(payload: dict = Body(...)):
    try:
        cleaned = [importer.clean(r) for r in payload.get("requirements", [])]
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    with db.db() as conn:
        for f in cleaned:
            _insert_requirement(conn, f)
        replan(conn, db.get_settings(conn))
    return {"added": len(cleaned)}


@app.delete("/api/requirements/{rid}")
def delete_requirement(rid: int):
    with db.db() as conn:
        conn.execute("DELETE FROM requirements WHERE id = ?", (rid,))
    touch()
    return {"ok": True}


@app.get("/api/requirements/template.csv")
def requirement_template():
    return PlainTextResponse(importer.TEMPLATE, media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="sample-schedule-template.csv"'})


@app.post("/api/requirements/import")
def import_requirements(file: UploadFile = File(...)):
    try:
        cleaned = importer.parse_table(file.filename or "upload.csv", file.file.read())
    except Exception as exc:
        raise HTTPException(400, f"Could not read that file: {exc}")
    for r in cleaned:
        r["allowed_months"] = json.loads(r["allowed_months"])
    return {"drafts": cleaned}


@app.get("/api/tasks")
def list_tasks(start: Optional[str] = None, end: Optional[str] = None):
    a = date.fromisoformat(start) if start else today() - timedelta(days=60)
    b = date.fromisoformat(end) if end else sampling.add_months(today(), sampling.HORIZON_MONTHS)
    with db.db() as conn:
        plan_if_needed(conn, db.get_settings(conn))
        return {"today": today().isoformat(), "tasks": sampling.tasks_between(conn, a, b)}


@app.put("/api/tasks/{task_id}")
def update_task(task_id: int, payload: dict = Body(...)):
    with db.db() as conn:
        settings = db.get_settings(conn)
        row = conn.execute("SELECT * FROM sample_tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "No such task")
        if payload.get("pull_date"):
            try:
                sampling.move_task(conn, settings, task_id, date.fromisoformat(payload["pull_date"]), today())
            except ValueError as exc:
                raise HTTPException(400, str(exc))
        if payload.get("unlock"):
            conn.execute("UPDATE sample_tasks SET locked = 0, pull_date = NULL, order_date = NULL WHERE id = ?", (task_id,))
        status = payload.get("status")
        if status in ("planned", "ordered", "pulled"):
            done = payload.get("completed_date") or today().isoformat() if status == "pulled" else None
            conn.execute("UPDATE sample_tasks SET status = ?, completed_date = ? WHERE id = ?", (status, done, task_id))
        if "notes" in payload:
            conn.execute("UPDATE sample_tasks SET notes = ? WHERE id = ?", (str(payload["notes"])[:1000], task_id))
        replan(conn, settings)
    return {"ok": True}


@app.post("/api/sampling/rebalance")
def rebalance():
    with db.db() as conn:
        sampling.rebalance(conn, db.get_settings(conn), today())
    touch()
    return {"ok": True}


@app.get("/api/sampling/budget")
def get_budget():
    with db.db() as conn:
        return sampling.budget(conn, db.get_settings(conn))


# --- Uploaded documents (permit, sample schedule) ---------------------------

def _store(upload: UploadFile, allowed: set) -> tuple:
    name = os.path.basename(upload.filename or "upload")
    ext = os.path.splitext(name)[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"{ext or 'That'} files are not accepted here ({', '.join(sorted(allowed))})")
    stored = uuid.uuid4().hex + ext
    with open(db.data_dir() / "uploads" / stored, "wb") as out:
        shutil.copyfileobj(upload.file, out)
    return name[:200], stored


def _upload_path(stored: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}\.[a-z0-9]{2,5}", stored):
        raise HTTPException(404, "Not found")
    path = db.data_dir() / "uploads" / stored
    if not path.exists():
        raise HTTPException(404, "Not found")
    return path


@app.get("/api/documents")
def list_documents():
    with db.db() as conn:
        return db.rows(conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC"))


@app.post("/api/documents")
def upload_document(file: UploadFile = File(...), kind: str = Form("permit")):
    name, stored = _store(file, DOC_TYPES)
    with db.db() as conn:
        cur = conn.execute("INSERT INTO documents (filename, stored, kind) VALUES (?, ?, ?)", (name, stored, kind[:30]))
    return {"id": cur.lastrowid}


@app.get("/api/documents/{doc_id}/file")
def download_document(doc_id: int):
    with db.db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Not found")
    return FileResponse(_upload_path(row["stored"]), filename=row["filename"], content_disposition_type="inline")


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int):
    with db.db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if row:
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            _upload_path(row["stored"]).unlink()
    return {"ok": True}


@app.post("/api/documents/{doc_id}/extract")
def extract_document(doc_id: int):
    """Draft requirements from a document. Nothing is saved until a person approves the drafts."""
    with db.db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Not found")
    path = _upload_path(row["stored"])
    try:
        if row["filename"].lower().endswith((".csv", ".xlsx")):
            drafts = importer.parse_table(row["filename"], path.read_bytes())
        elif not importer.ai_enabled():
            raise HTTPException(400, "Reading a PDF automatically needs an Anthropic API key (see docs/software-setup.md). "
                                     "Without one, fill in the spreadsheet template and import that.")
        else:
            drafts = importer.extract_with_claude(path, row["filename"])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Could not read that document: {exc}")
    for d in drafts:
        d["allowed_months"] = json.loads(d["allowed_months"])
    return {"drafts": drafts}


# --- GIFs and videos --------------------------------------------------------

@app.get("/api/media")
def list_media():
    with db.db() as conn:
        return db.rows(conn.execute("SELECT * FROM media ORDER BY kind, id DESC"))


def _media_fields(p: dict) -> dict:
    out = {}
    for key in ("title", "condition", "screen"):
        if key in p:
            out[key] = str(p[key] or "")[:80]
    for key in ("start_date", "end_date"):
        if key in p:
            out[key] = date.fromisoformat(p[key]).isoformat() if p[key] else None
    if "interval_min" in p:
        out["interval_min"] = max(1, int(p["interval_min"] or 30))
    for key in ("muted", "active"):
        if key in p:
            out[key] = 1 if str(p[key]).lower() in ("1", "true", "on", "yes") else 0
    if out.get("screen") not in (None, "left", "right", "both"):
        out["screen"] = "both"
    return out


@app.post("/api/media")
def upload_media(file: UploadFile = File(...), kind: str = Form(...), title: str = Form(""),
                 condition: str = Form("any"), start_date: str = Form(""), end_date: str = Form(""),
                 screen: str = Form("both"), interval_min: int = Form(30), muted: str = Form("1")):
    if kind not in MEDIA_TYPES:
        raise HTTPException(400, "kind must be gif or video")
    name, stored = _store(file, MEDIA_TYPES[kind])
    try:
        f = _media_fields({"title": title or name, "condition": condition, "start_date": start_date,
                           "end_date": end_date, "screen": screen, "interval_min": interval_min, "muted": muted})
    except ValueError:
        raise HTTPException(400, "Dates must look like 2026-12-01")
    with db.db() as conn:
        conn.execute(
            "INSERT INTO media (title, filename, stored, kind, condition, start_date, end_date, screen, interval_min, muted) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (f["title"], name, stored, kind, f["condition"] or "any", f["start_date"], f["end_date"], f["screen"],
             f["interval_min"], f["muted"]))
    touch()
    return {"ok": True}


@app.put("/api/media/{media_id}")
def update_media(media_id: int, payload: dict = Body(...)):
    try:
        f = _media_fields(payload)
    except ValueError:
        raise HTTPException(400, "Dates must look like 2026-12-01")
    if f:
        with db.db() as conn:
            conn.execute(f"UPDATE media SET {', '.join(k + ' = ?' for k in f)} WHERE id = ?", list(f.values()) + [media_id])
    touch()
    return {"ok": True}


@app.delete("/api/media/{media_id}")
def delete_media(media_id: int):
    with db.db() as conn:
        row = conn.execute("SELECT * FROM media WHERE id = ?", (media_id,)).fetchone()
        if row:
            conn.execute("DELETE FROM media WHERE id = ?", (media_id,))
            _upload_path(row["stored"]).unlink()
    touch()
    return {"ok": True}


@app.get("/media/{stored}")
def media_file(stored: str):
    return FileResponse(_upload_path(stored), headers={"Cache-Control": "max-age=86400"})


@app.get("/api/ambient")
def ambient(screen: str = "left"):
    """What a wall screen should show besides the calendar: weather, GIFs, videos, seasonal effect."""
    iso = today().isoformat()
    with db.db() as conn:
        settings = db.get_settings(conn)
        gifs = db.rows(conn.execute("SELECT * FROM media WHERE kind = 'gif' AND active = 1"))
        videos = db.rows(conn.execute(
            "SELECT * FROM media WHERE kind = 'video' AND active = 1 AND screen IN (?, 'both') "
            "AND (start_date IS NULL OR start_date <= ?) AND (end_date IS NULL OR end_date >= ?) ORDER BY id",
            (screen, iso, iso)))
    now = weather.current(settings)
    chosen = []
    for tag in (now["tags"] if now else []) + ["any"]:
        chosen = [g for g in gifs if g["condition"] == tag]
        if chosen:
            break
    effect = settings.get("season_effect", "weather")
    if effect == "weather" and not now:
        effect = "auto"                      # no weather source yet: fall back to the season
    if effect == "auto":
        season = weather.season_for(today())
        effect = {"fall": "leaves", "winter": "snow", "spring": "petals", "summer": "bubbles"}[season]
        if now and now["condition"] == "snow":
            effect = "snow"
    return {"weather": now, "effect": effect, "gif_seconds": settings.get("gif_seconds", 45),
            "pixel_shift": bool(settings.get("pixel_shift", True)),
            "gifs": [{"url": "/media/" + g["stored"], "title": g["title"]} for g in chosen],
            "videos": [{"id": v["id"], "url": "/media/" + v["stored"], "title": v["title"],
                        "interval_min": v["interval_min"], "muted": bool(v["muted"])} for v in videos]}


# --- Export -----------------------------------------------------------------

@app.get("/api/export.md")
def export_markdown(start: str, end: str, download: int = 0):
    try:
        a, b = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        raise HTTPException(400, "Dates must look like 2026-11-14")
    if b < a or (b - a).days > 3700:
        raise HTTPException(400, "Pick an end date after the start date, at most ten years apart")
    with db.db() as conn:
        settings = db.get_settings(conn)
        plan_if_needed(conn, settings)
        text = exporter.markdown(conn, settings, a, b, today())
    headers = {"Content-Disposition": f'attachment; filename="calendar-{start}-to-{end}.md"'} if download else {}
    return PlainTextResponse(text, media_type="text/markdown; charset=utf-8", headers=headers)
