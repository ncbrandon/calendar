"""Sampling requirements -> dated tasks (order bottles, pull sample, deadline).

A requirement says "N samples every <period>". Each period gets N tasks. Short
periods (weekly, monthly) are placed evenly inside the period. Long periods
(quarterly up to nine years) are placed in whichever allowed month keeps the
cost per budget year, and then per month, as level as possible, while finishing
early enough to leave room for a resample before the deadline.

Dates a person sets are "locked" and are never moved by the planner.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from typing import Iterator, Optional

from . import holidays

# frequency -> (unit, length)
FREQUENCIES = {
    "weekly": ("days", 7),
    "monthly": ("months", 1),
    "quarterly": ("months", 3),
    "semiannual": ("months", 6),
    "annual": ("months", 12),
    "triennial": ("months", 36),
    "six_year": ("months", 72),
    "nine_year": ("months", 108),
    "once": ("once", 0),
}
FREQUENCY_LABELS = {
    "weekly": "Weekly",
    "monthly": "Monthly",
    "quarterly": "Quarterly",
    "semiannual": "Twice a year",
    "annual": "Yearly",
    "triennial": "Every 3 years",
    "six_year": "Every 6 years",
    "nine_year": "Every 9 years",
    "once": "One time",
}
HORIZON_MONTHS = 36


def add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    last = (nxt - timedelta(days=1)).day
    return date(year, month, min(day.day, last))


def fiscal_year(day: date, start_month: int) -> int:
    """Fiscal years are named for the calendar year they end in."""
    if start_month <= 1:
        return day.year
    return day.year + 1 if day.month >= start_month else day.year


def periods(req: dict, start: date, end: date) -> Iterator[tuple]:
    """Yield (period_start, period_end) for every period overlapping [start, end]."""
    anchor = date.fromisoformat(req["anchor_date"])
    stop = date.fromisoformat(req["end_date"]) if req.get("end_date") else None
    unit, length = FREQUENCIES[req["frequency"]]
    if unit == "once":
        last = stop or add_months(anchor, 12) - timedelta(days=1)
        if anchor <= end and last >= start:
            yield anchor, last
        return
    k = 0
    if start > anchor:
        if unit == "days":
            k = (start - anchor).days // length
        else:
            months = (start.year - anchor.year) * 12 + start.month - anchor.month
            k = max(0, months // length - 1)
    while True:
        if unit == "days":
            ps = anchor + timedelta(days=k * length)
            pe = ps + timedelta(days=length - 1)
        else:
            ps = add_months(anchor, k * length)
            pe = add_months(anchor, (k + 1) * length) - timedelta(days=1)
        if ps > end or (stop and ps > stop):
            return
        if pe >= start:
            yield ps, pe
        k += 1


class _Days:
    """Answers "is this a holiday / a valid pull day / a workday?" with caching."""

    def __init__(self, conn, settings: dict):
        self.conn, self.settings, self.cache = conn, settings, {}
        self.pull_weekdays = set(settings.get("pull_weekdays") or [0, 1, 2])

    def is_holiday(self, day: date) -> bool:
        if day.year not in self.cache:
            self.cache[day.year] = set(
                holidays.between(self.conn, self.settings, date(day.year, 1, 1), date(day.year, 12, 31))
            )
        return day.isoformat() in self.cache[day.year]

    def pull_ok(self, day: date) -> bool:
        return day.weekday() in self.pull_weekdays and not self.is_holiday(day)

    def next_pull_day(self, day: date, limit: date) -> Optional[date]:
        while day <= limit:
            if self.pull_ok(day):
                return day
            day += timedelta(days=1)
        return None

    def workday_on_or_before(self, day: date) -> date:
        while day.weekday() > 4 or self.is_holiday(day):
            day -= timedelta(days=1)
        return day


def ensure_tasks(conn, settings: dict, today: date) -> None:
    """Create any missing tasks out to the planning horizon, then place them."""
    horizon = add_months(today, HORIZON_MONTHS)
    for row in conn.execute("SELECT * FROM requirements WHERE active = 1"):
        req = dict(row)
        for ps, pe in periods(req, today, horizon):
            for seq in range(1, int(req["samples_per_period"]) + 1):
                conn.execute(
                    "INSERT OR IGNORE INTO sample_tasks (requirement_id, period_start, period_end, seq) "
                    "VALUES (?, ?, ?, ?)",
                    (req["id"], ps.isoformat(), pe.isoformat(), seq),
                )
    # Drop open, unlocked tasks that no longer belong to an active requirement.
    conn.execute(
        "DELETE FROM sample_tasks WHERE status = 'planned' AND locked = 0 AND ("
        " requirement_id IN (SELECT id FROM requirements WHERE active = 0)"
        " OR seq > (SELECT samples_per_period FROM requirements r WHERE r.id = requirement_id))"
    )
    place(conn, settings, today)


def reset_requirement(conn, requirement_id: int) -> None:
    """Forget the auto-planned tasks of one requirement (after it was edited)."""
    conn.execute(
        "DELETE FROM sample_tasks WHERE requirement_id = ? AND status = 'planned' AND locked = 0",
        (requirement_id,),
    )


def rebalance(conn, settings: dict, today: date) -> None:
    """Re-plan every future task that a person has not pinned or started."""
    conn.execute(
        "UPDATE sample_tasks SET pull_date = NULL, order_date = NULL "
        "WHERE status = 'planned' AND locked = 0 AND (pull_date IS NULL OR pull_date >= ?)",
        (today.isoformat(),),
    )
    ensure_tasks(conn, settings, today)


def place(conn, settings: dict, today: date) -> None:
    """Give a pull date and bottle-order date to every task that has none."""
    days = _Days(conn, settings)
    fy_start = int(settings.get("fiscal_year_start_month") or 1)
    buffer_setting = int(settings.get("deadline_buffer_months") or 0)
    day_min = int(settings.get("sampling_day_min") or 1)

    tasks = [
        dict(r)
        for r in conn.execute(
            "SELECT t.*, r.frequency, r.cost, r.lead_days, r.allowed_months, r.samples_per_period "
            "FROM sample_tasks t JOIN requirements r ON r.id = t.requirement_id"
        )
    ]
    month_load, month_count, fy_load, same = defaultdict(float), defaultdict(int), defaultdict(float), defaultdict(int)
    pulls = defaultdict(list)   # requirement -> month numbers already used, to keep repeats apart

    def book(task: dict, day: date) -> None:
        weight = task["cost"] if task["cost"] > 0 else 1.0
        ym = day.strftime("%Y-%m")
        month_load[ym] += weight
        month_count[ym] += 1
        fy_load[fiscal_year(day, fy_start)] += weight
        same[(task["requirement_id"], ym)] += 1
        pulls[task["requirement_id"]].append(day.year * 12 + day.month)

    def fy_capacity(day: date) -> float:
        """Share of that fiscal year still ahead of us (so a nearly-over year gets a small share)."""
        fy = fiscal_year(day, fy_start)
        if fy != fiscal_year(today, fy_start):
            return 1.0
        remaining, probe = 0, date(today.year, today.month, 1)
        while fiscal_year(probe, fy_start) == fy:
            remaining += 1
            probe = add_months(probe, 1)
        return remaining / 12.0

    for task in tasks:
        if task["pull_date"]:
            book(task, date.fromisoformat(task["completed_date"] or task["pull_date"]))

    def period_months(task: dict) -> int:
        unit, length = FREQUENCIES[task["frequency"]]
        if unit == "months":
            return length
        ps, pe = date.fromisoformat(task["period_start"]), date.fromisoformat(task["period_end"])
        return 0 if unit == "days" else max(1, round((pe - ps).days / 30.4))

    todo = [t for t in tasks if not t["pull_date"]]
    todo.sort(key=lambda t: (period_months(t), t["period_end"], -t["cost"], t["requirement_id"], t["seq"]))

    for task in todo:
        ps, pe = date.fromisoformat(task["period_start"]), date.fromisoformat(task["period_end"])
        lead = int(task["lead_days"] or 0)
        earliest = max(ps, today + timedelta(days=lead))
        months = period_months(task)
        pull = None

        if months <= 1:
            # Short period: spread the samples evenly through it.
            length = (pe - ps).days + 1
            target = ps + timedelta(days=int(length * (task["seq"] - 0.5) / task["samples_per_period"]))
            if months == 1:
                target = max(target, ps + timedelta(days=min(day_min, length) - 1)) if task["samples_per_period"] == 1 else target
            pull = days.next_pull_day(target, pe) or days.next_pull_day(ps, pe)
            if pull is None or pull < today:
                conn.execute("DELETE FROM sample_tasks WHERE id = ?", (task["id"],))
                continue
        else:
            allowed = set(json.loads(task["allowed_months"] or "[]"))
            buffer = min(buffer_setting, months // 4)
            last_ok = add_months(pe + timedelta(days=1), -buffer) - timedelta(days=1)
            best = None
            month = date(earliest.year, earliest.month, 1)
            while month <= pe:
                month_end = add_months(month, 1) - timedelta(days=1)
                first = max(month.replace(day=min(day_min, month_end.day)), earliest, ps)
                day = days.next_pull_day(first, min(month_end, pe))
                if day:
                    ok_month = not allowed or month.month in allowed
                    tier = 0 if (ok_month and day <= last_ok) else (1 if ok_month else 2)
                    weight = task["cost"] if task["cost"] > 0 else 1.0
                    ym = month.strftime("%Y-%m")
                    fy_score = round((fy_load[fiscal_year(day, fy_start)] + weight) / fy_capacity(day), 2)
                    # Do not put this year's sample right next to last year's: keep repeats ~6 months apart.
                    gap = min(months // 2, 6)
                    index = month.year * 12 + month.month
                    crowded = any(abs(index - other) < gap for other in pulls[task["requirement_id"]])
                    key = (tier, same[(task["requirement_id"], ym)], crowded, fy_score, month_load[ym], month_count[ym], ym)
                    if best is None or key < best[0]:
                        best = (key, day)
                month = add_months(month, 1)
            if best:
                pull = best[1]
            else:
                # The window is closed or closing: do it as soon as the bottles can be here.
                pull = days.next_pull_day(earliest, earliest + timedelta(days=30)) or earliest

        order = None
        if lead > 0:
            order = max(days.workday_on_or_before(pull - timedelta(days=lead)), today)
        conn.execute(
            "UPDATE sample_tasks SET pull_date = ?, order_date = ? WHERE id = ?",
            (pull.isoformat(), order.isoformat() if order else None, task["id"]),
        )
        book(task, pull)


def move_task(conn, settings: dict, task_id: int, pull: date, today: date) -> None:
    """A person picked the pull date: pin it and re-derive the bottle-order date."""
    row = conn.execute(
        "SELECT t.id, r.lead_days FROM sample_tasks t JOIN requirements r ON r.id = t.requirement_id WHERE t.id = ?",
        (task_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Unknown task")
    order = None
    if row["lead_days"] > 0:
        order = _Days(conn, settings).workday_on_or_before(pull - timedelta(days=row["lead_days"]))
    conn.execute(
        "UPDATE sample_tasks SET pull_date = ?, order_date = ?, locked = 1 WHERE id = ?",
        (pull.isoformat(), order.isoformat() if order else None, task_id),
    )


def tasks_between(conn, start: date, end: date) -> list:
    """Every task with an order date, pull date, or deadline inside [start, end]."""
    a, b = start.isoformat(), end.isoformat()
    return [
        dict(r)
        for r in conn.execute(
            "SELECT t.*, r.name, r.program, r.location, r.frequency, r.cost, r.lab, r.lead_days "
            "FROM sample_tasks t JOIN requirements r ON r.id = t.requirement_id "
            "WHERE (t.pull_date BETWEEN ? AND ?) OR (t.order_date BETWEEN ? AND ?) "
            "   OR (t.period_end BETWEEN ? AND ?) OR (t.completed_date BETWEEN ? AND ?) "
            "ORDER BY COALESCE(t.pull_date, t.period_end), r.name, t.seq",
            (a, b, a, b, a, b, a, b),
        )
    ]


def calendar_items(conn, start: date, end: date, today: date) -> dict:
    """Map of ISO date -> list of calendar items for the sampling tasks."""
    out = defaultdict(list)
    a, b = start.isoformat(), end.isoformat()
    deadlines = set()
    for t in tasks_between(conn, start, end):
        label = t["name"] + (f" #{t['seq']}" if t["seq"] > 1 else "")
        pulled = t["status"] == "pulled"
        base = {"task_id": t["id"], "status": t["status"], "location": t["location"], "cost": t["cost"],
                "locked": t["locked"], "pull_date": t["pull_date"], "period_end": t["period_end"]}
        if t["order_date"] and a <= t["order_date"] <= b:
            out[t["order_date"]].append(dict(base, type="order", title=f"Order bottles: {label}",
                                             done=t["status"] != "planned"))
        shown = t["completed_date"] if pulled and t["completed_date"] else t["pull_date"]
        if shown and a <= shown <= b:
            out[shown].append(dict(base, type="pull", title=f"Pull sample: {label}", done=pulled,
                                   overdue=(not pulled and shown < today.isoformat())))
        long_window = FREQUENCIES[t["frequency"]][1] >= 12 or t["frequency"] == "once"
        key = (t["requirement_id"], t["period_end"])
        if long_window and not pulled and a <= t["period_end"] <= b and key not in deadlines:
            deadlines.add(key)
            out[t["period_end"]].append(dict(base, type="deadline", title=f"DEADLINE: {t['name']}", done=False))
    return out


def budget(conn, settings: dict) -> dict:
    """Planned and spent sampling cost by fiscal year and by month."""
    fy_start = int(settings.get("fiscal_year_start_month") or 1)
    years, months = defaultdict(lambda: {"planned": 0.0, "done": 0.0, "count": 0}), defaultdict(float)
    for r in conn.execute(
        "SELECT t.pull_date, t.completed_date, t.status, r.cost FROM sample_tasks t "
        "JOIN requirements r ON r.id = t.requirement_id WHERE t.pull_date IS NOT NULL"
    ):
        day = date.fromisoformat(r["completed_date"] or r["pull_date"])
        bucket = years[fiscal_year(day, fy_start)]
        bucket["done" if r["status"] == "pulled" else "planned"] += r["cost"]
        bucket["count"] += 1
        months[day.strftime("%Y-%m")] += r["cost"]
    return {
        "years": [dict(year=y, **v, total=v["planned"] + v["done"]) for y, v in sorted(years.items())],
        "months": [{"month": m, "total": v} for m, v in sorted(months.items())],
    }
