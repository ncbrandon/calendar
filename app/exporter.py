"""Markdown export of everything on the calendar between two dates."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from . import holidays, rotation, sampling


def _fmt(day: date) -> str:
    return f"{day.strftime('%a %b')} {day.day}, {day.year}"


def markdown(conn, settings: dict, start: date, end: date, today: date) -> str:
    names = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM employees")}
    hol = holidays.between(conn, settings, start, end)
    oncall = rotation.oncall_between(conn, settings, start, end)
    who = lambda iso: names.get(oncall[iso]["employee_id"], "unassigned")
    out = [
        f"# {settings['site_name']} - calendar export",
        "",
        f"- **Range:** {_fmt(start)} to {_fmt(end)}",
        f"- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    # --- On-call weeks -----------------------------------------------------
    out += ["## On-call schedule", "", "| Week | On call | Changes inside the week |", "|---|---|---|"]
    start_wd = settings.get("rotation_start_weekday", 3)
    week = rotation.week_start(start, start_wd)
    while week <= end:
        days = [week + timedelta(days=i) for i in range(7)]
        inside = [d for d in days if start <= d <= end]
        people = [who(d.isoformat()) for d in inside]
        main = max(set(people), key=people.count)
        changes = ", ".join(f"{d.strftime('%a')} {d.month}/{d.day}: {p}" for d, p in zip(inside, people) if p != main)
        out.append(f"| {_fmt(days[0])} to {_fmt(days[-1])} | {main} | {changes or '-'} |")
        week += timedelta(days=7)
    out.append("")

    # --- Holidays and weekends --------------------------------------------
    out += ["## Holidays", ""]
    if hol:
        out += ["| Date | Holiday | On call |", "|---|---|---|"]
        out += [f"| {_fmt(date.fromisoformat(iso))} | {name} | {who(iso)} |" for iso, name in sorted(hol.items())]
    else:
        out.append("_None in this range._")
    counts = defaultdict(lambda: {"weekend": 0, "holiday": 0})
    day = start
    while day <= end:
        iso = day.isoformat()
        if day.weekday() >= 5:
            counts[who(iso)]["weekend"] += 1
        if iso in hol:
            counts[who(iso)]["holiday"] += 1
        day += timedelta(days=1)
    out += ["", "### Weekend and holiday days worked", "", "| Employee | Weekend days | Holidays |", "|---|---|---|"]
    out += [f"| {name} | {c['weekend']} | {c['holiday']} |" for name, c in sorted(counts.items())]
    out.append("")

    # --- Pay weeks ---------------------------------------------------------
    pay_start = settings.get("pay_week_start", 6)
    out += ["## Pay weeks", "", "| Begins | Ends |", "|---|---|"]
    week = rotation.week_start(start, pay_start)
    while week <= end:
        out.append(f"| {_fmt(week)} | {_fmt(week + timedelta(days=6))} |")
        week += timedelta(days=7)
    out.append("")

    # --- Sampling ----------------------------------------------------------
    out += ["## Sampling", ""]
    tasks = sampling.tasks_between(conn, start, end)
    if tasks:
        out += ["| Order bottles | Pull sample | Requirement | Location | Window ends | Status | Cost |", "|---|---|---|---|---|---|---|"]
        total = 0.0
        for t in tasks:
            status = t["status"]
            if status == "pulled":
                status = f"pulled {t['completed_date'] or ''}".strip()
            elif t["pull_date"] and t["pull_date"] < today.isoformat():
                status = "OVERDUE"
            total += t["cost"]
            label = t["name"] + (f" #{t['seq']}" if t["seq"] > 1 else "")
            out.append(
                f"| {t['order_date'] or '-'} | {t['pull_date'] or '-'} | {label} | {t['location'] or '-'} "
                f"| {t['period_end']} | {status} | ${t['cost']:,.2f} |"
            )
        out += ["", f"**Sampling cost in this range:** ${total:,.2f}"]
    else:
        out.append("_No sampling tasks in this range._")
    out.append("")

    # --- Events, month by month -------------------------------------------
    out += ["## Events", ""]
    events = conn.execute(
        "SELECT * FROM events WHERE date <= ? AND COALESCE(end_date, date) >= ? ORDER BY date, COALESCE(time, ''), id",
        (end.isoformat(), start.isoformat()),
    ).fetchall()
    if not events:
        out.append("_No events in this range._")
    month = None
    for e in events:
        day = date.fromisoformat(e["date"])
        if day.strftime("%Y-%m") != month:
            month = day.strftime("%Y-%m")
            out += ["", f"### {day.strftime('%B %Y')}", ""]
        line = f"- [{'x' if e['done'] else ' '}] **{_fmt(day)}**"
        if e["end_date"] and e["end_date"] != e["date"]:
            line += f" to **{_fmt(date.fromisoformat(e['end_date']))}**"
        if e["time"]:
            line += f" {e['time']}"
        line += f" - {e['title']} _({e['category']})_"
        out.append(line)
        if e["notes"]:
            out.append(f"  - {e['notes']}")
    out.append("")
    return "\n".join(out)
