"""On-call rotation.

The on-call week runs from the rotation start weekday (Thursday by default)
through the day before it the following week (Wednesday).

* Picking a rotation employee on a Thursday starts the rotation there: that
  person gets Thursday-Wednesday, then the rotation employees alternate
  automatically, week after week.
* Picking someone who is not in the rotation (Brandon) on a Thursday covers
  that one week only. The rotation carries on underneath as if nothing happened.
* Picking anyone on any other day changes just that one day.
* Picking "Auto" removes the manual choice (the whole week if done on Thursday).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional


def week_start(day: date, start_weekday: int = 3) -> date:
    return day - timedelta(days=(day.weekday() - start_weekday) % 7)


def _rotation_ids(conn) -> list:
    return [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM employees WHERE in_rotation = 1 AND active = 1 ORDER BY sort, id"
        )
    ]


def oncall_between(conn, settings: dict, start: date, end: date) -> dict:
    """Map of ISO date -> {"employee_id": int | None, "source": "rotation" | "override" | None}."""
    start_wd = settings.get("rotation_start_weekday", 3)
    ids = _rotation_ids(conn)
    anchors = [
        (date.fromisoformat(r["week_start"]), r["employee_id"])
        for r in conn.execute("SELECT week_start, employee_id FROM rotation_anchors ORDER BY week_start")
    ]
    overrides = {
        r["day"]: r["employee_id"]
        for r in conn.execute(
            "SELECT day, employee_id FROM oncall_overrides WHERE day BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat()),
        )
    }
    out = {}
    day = start
    while day <= end:
        iso = day.isoformat()
        if iso in overrides:
            out[iso] = {"employee_id": overrides[iso], "source": "override"}
        else:
            ws = week_start(day, start_wd)
            anchor = None
            for a in anchors:
                if a[0] <= ws:
                    anchor = a
                else:
                    break
            if anchor and ids:
                first = ids.index(anchor[1]) if anchor[1] in ids else 0
                weeks = (ws - anchor[0]).days // 7
                out[iso] = {"employee_id": ids[(first + weeks) % len(ids)], "source": "rotation"}
            else:
                out[iso] = {"employee_id": None, "source": None}
        day += timedelta(days=1)
    return out


def set_oncall(conn, settings: dict, day: date, employee_id: Optional[int]) -> None:
    start_wd = settings.get("rotation_start_weekday", 3)
    is_week_start = day.weekday() == start_wd
    week = [(day + timedelta(days=i)).isoformat() for i in range(7)]
    marks = ",".join("?" * 7)

    if employee_id is None:  # "Auto"
        if is_week_start:
            conn.execute(f"DELETE FROM oncall_overrides WHERE day IN ({marks})", week)
        else:
            conn.execute("DELETE FROM oncall_overrides WHERE day = ?", (day.isoformat(),))
        return

    emp = conn.execute("SELECT id, in_rotation FROM employees WHERE id = ?", (employee_id,)).fetchone()
    if emp is None:
        raise ValueError("Unknown employee")

    if is_week_start and emp["in_rotation"]:
        # Restart the rotation from this week; later weeks alternate from here.
        conn.execute("DELETE FROM rotation_anchors WHERE week_start >= ?", (day.isoformat(),))
        conn.execute(
            "INSERT INTO rotation_anchors (week_start, employee_id) VALUES (?, ?)",
            (day.isoformat(), employee_id),
        )
        conn.execute(f"DELETE FROM oncall_overrides WHERE day IN ({marks})", week)
    elif is_week_start:
        # Cover one whole week without disturbing the rotation.
        for iso in week:
            conn.execute(
                "INSERT INTO oncall_overrides (day, employee_id) VALUES (?, ?) "
                "ON CONFLICT(day) DO UPDATE SET employee_id = excluded.employee_id",
                (iso, employee_id),
            )
    else:
        conn.execute(
            "INSERT INTO oncall_overrides (day, employee_id) VALUES (?, ?) "
            "ON CONFLICT(day) DO UPDATE SET employee_id = excluded.employee_id",
            (day.isoformat(), employee_id),
        )
