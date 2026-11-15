"""SQLite storage: schema, defaults, and small helpers."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS employees (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  color TEXT NOT NULL DEFAULT '#4f8cc9',
  in_rotation INTEGER NOT NULL DEFAULT 0,
  sort INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1
);

-- A rotation anchor says "this employee starts the rotation on this week-start day".
CREATE TABLE IF NOT EXISTS rotation_anchors (
  week_start TEXT PRIMARY KEY,
  employee_id INTEGER NOT NULL REFERENCES employees(id)
);

-- A single-day override of whoever the rotation would have picked.
CREATE TABLE IF NOT EXISTS oncall_overrides (
  day TEXT PRIMARY KEY,
  employee_id INTEGER NOT NULL REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  date TEXT NOT NULL,
  end_date TEXT,
  time TEXT,
  category TEXT NOT NULL DEFAULT 'general',
  notes TEXT NOT NULL DEFAULT '',
  done INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'web',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);

CREATE TABLE IF NOT EXISTS holidays (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  name TEXT NOT NULL,
  end_date TEXT,                      -- last day, for a holiday that runs several days
  yearly INTEGER NOT NULL DEFAULT 0   -- 1 = same dates every year
);

CREATE TABLE IF NOT EXISTS requirements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  program TEXT NOT NULL DEFAULT 'drinking',
  location TEXT NOT NULL DEFAULT '',
  frequency TEXT NOT NULL DEFAULT 'triennial',
  anchor_date TEXT NOT NULL,
  end_date TEXT,
  samples_per_period INTEGER NOT NULL DEFAULT 1,
  allowed_months TEXT NOT NULL DEFAULT '[]',
  cost REAL NOT NULL DEFAULT 0,
  lead_days INTEGER NOT NULL DEFAULT 14,
  lab TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sample_tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  requirement_id INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  seq INTEGER NOT NULL DEFAULT 1,
  pull_date TEXT,
  order_date TEXT,
  status TEXT NOT NULL DEFAULT 'planned',   -- planned | ordered | pulled
  locked INTEGER NOT NULL DEFAULT 0,        -- 1 = date set by a person, never auto-moved
  completed_date TEXT,
  notes TEXT NOT NULL DEFAULT '',
  UNIQUE (requirement_id, period_start, seq)
);

CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT NOT NULL,
  stored TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'permit',
  uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS media (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL DEFAULT '',
  filename TEXT NOT NULL,
  stored TEXT NOT NULL,
  kind TEXT NOT NULL,                        -- gif | video
  condition TEXT NOT NULL DEFAULT 'any',     -- gif: which weather it is for
  start_date TEXT,                           -- video: first day it plays
  end_date TEXT,                             -- video: last day it plays
  screen TEXT NOT NULL DEFAULT 'both',       -- left | right | both
  interval_min INTEGER NOT NULL DEFAULT 30,  -- video: play every N minutes
  muted INTEGER NOT NULL DEFAULT 1,
  active INTEGER NOT NULL DEFAULT 1
);
"""

# Weekdays everywhere in this app: Monday = 0 ... Sunday = 6.
DEFAULT_SETTINGS = {
    "site_name": "Water & Wastewater Operations",
    "latitude": None,
    "longitude": None,
    "temp_unit": "F",
    "work_days": [0, 1, 2, 3, 4],
    "work_start": "07:00",
    "work_end": "16:30",
    "wake_minutes": 5,            # how long a tap keeps a dark screen on
    "idle_return_minutes": 3,     # arrows snap back to the current month after this
    "rotation_start_weekday": 3,  # Thursday
    "pay_week_start": 6,          # Sunday; the pay week ends the day before
    "payday_weekday": 4,          # Friday; None hides the payday tag
    "federal_holidays": True,
    "holiday_exclude": [],        # names of federal holidays you do not observe
    "holiday_extra": [],          # extra days off you do get, e.g. "Day after Thanksgiving", "Christmas Eve"
    "fiscal_year_start_month": 1,
    "pull_weekdays": [0, 1, 2],   # Mon-Wed, so the lab has the samples before the weekend
    "sampling_day_min": 8,        # monthly "sampling day" is the first pull weekday on/after this day
    "deadline_buffer_months": 6,  # finish long-window samples this early to leave room for a resample
    "station_url": "",            # your own weather station's website (WeeWX with the Belchertown skin)
    "season_effect": "weather",   # weather (follow current conditions) | auto (season) | leaves | snow | petals | bubbles | off
    "pixel_shift": True,          # nudge the whole picture a few pixels every few minutes
    "gif_seconds": 45,            # how long each weather GIF stays up
}

EMPLOYEE_SEED = [
    ("Jody", "#2f9e77", 1, 0),
    ("Marcus", "#3b7dd8", 1, 1),
    ("Brandon", "#c9762b", 0, 2),
]


def data_dir() -> Path:
    default = Path(__file__).resolve().parent.parent / "data"
    path = Path(os.environ.get("OPSBOARD_DATA", default))
    (path / "uploads").mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(data_dir() / "opsboard.db"), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)
        # Databases made before multi-day holidays existed.
        have = {r["name"] for r in conn.execute("PRAGMA table_info(holidays)")}
        if "end_date" not in have:
            conn.execute("ALTER TABLE holidays ADD COLUMN end_date TEXT")
        if "yearly" not in have:
            conn.execute("ALTER TABLE holidays ADD COLUMN yearly INTEGER NOT NULL DEFAULT 0")
        if conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO employees (name, color, in_rotation, sort) VALUES (?,?,?,?)",
                EMPLOYEE_SEED,
            )


def get_settings(conn) -> dict:
    out = dict(DEFAULT_SETTINGS)
    for row in conn.execute("SELECT key, value FROM settings"):
        if row["key"] in DEFAULT_SETTINGS:
            out[row["key"]] = json.loads(row["value"])
    return out


def set_settings(conn, values: dict) -> None:
    for key, value in values.items():
        if key in DEFAULT_SETTINGS:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value)),
            )


def get_secret(conn, key: str) -> str:
    """Return a stored random secret, creating it on first use."""
    row = conn.execute("SELECT value FROM settings WHERE key = ?", ("_" + key,)).fetchone()
    if row:
        return json.loads(row["value"])
    import secrets

    value = secrets.token_hex(32)
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("_" + key, json.dumps(value)))
    return value


def rows(cursor) -> list:
    return [dict(r) for r in cursor.fetchall()]
