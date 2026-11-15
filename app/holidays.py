"""US federal holidays (computed) plus the custom ones stored in the database."""
from __future__ import annotations

from datetime import date, timedelta


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def last_weekday(year: int, month: int, weekday: int) -> date:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def federal(year: int) -> dict:
    """Map of date -> name, including the Friday/Monday 'observed' days."""
    fixed = {
        date(year, 1, 1): "New Year's Day",
        date(year, 6, 19): "Juneteenth",
        date(year, 7, 4): "Independence Day",
        date(year, 11, 11): "Veterans Day",
        date(year, 12, 25): "Christmas Day",
    }
    out = {
        nth_weekday(year, 1, 0, 3): "Martin Luther King Jr. Day",
        nth_weekday(year, 2, 0, 3): "Presidents' Day",
        last_weekday(year, 5, 0): "Memorial Day",
        nth_weekday(year, 9, 0, 1): "Labor Day",
        nth_weekday(year, 10, 0, 2): "Columbus Day",
        nth_weekday(year, 11, 3, 4): "Thanksgiving Day",
    }
    for day, name in fixed.items():
        out[day] = name
        if day.weekday() == 5:
            out.setdefault(day - timedelta(days=1), name + " (observed)")
        elif day.weekday() == 6:
            out.setdefault(day + timedelta(days=1), name + " (observed)")
    return out


def extra(year: int) -> dict:
    """Extra days off many employers give around the big holidays. Each is switched on by name in Settings."""
    return {
        nth_weekday(year, 11, 3, 4) + timedelta(days=1): "Day after Thanksgiving",
        date(year, 12, 24): "Christmas Eve",
        date(year, 12, 26): "Day after Christmas",
        date(year, 12, 31): "New Year's Eve",
    }


EXTRA_NAMES = list(extra(2026).values())


def _same_day(day: date, year: int) -> date:
    try:
        return day.replace(year=year)
    except ValueError:            # Feb 29 in a year without one
        return date(year, 2, 28)


def detail(conn, settings: dict, start: date, end: date) -> dict:
    """Map of ISO date -> {"name", "id"} for every holiday in [start, end]. id is set for your own holidays."""
    out = {}
    if settings.get("federal_holidays", True):
        excluded = set(settings.get("holiday_exclude") or [])
        # year + 1 picks up a New Year's Day observed on Dec 31.
        for year in range(start.year, end.year + 2):
            for day, name in federal(year).items():
                base = name.replace(" (observed)", "")
                if start <= day <= end and base not in excluded:
                    out[day.isoformat()] = {"name": name, "id": None}
    wanted = set(settings.get("holiday_extra") or [])
    for year in range(start.year, end.year + 1):
        for day, name in extra(year).items():
            if name in wanted and start <= day <= end:
                out[day.isoformat()] = {"name": name, "id": None}
    # Your own holidays: one day or a run of days, once or every year on the same dates.
    for row in conn.execute("SELECT id, date, end_date, name, yearly FROM holidays ORDER BY date, id"):
        first = date.fromisoformat(row["date"])
        length = (date.fromisoformat(row["end_date"]) - first).days if row["end_date"] else 0
        years = range(max(first.year, start.year - 1), end.year + 1) if row["yearly"] else [first.year]
        for year in years:
            begin = _same_day(first, year)
            for n in range(length + 1):
                day = begin + timedelta(days=n)
                if start <= day <= end:
                    out[day.isoformat()] = {"name": row["name"], "id": row["id"]}
    return out


def between(conn, settings: dict, start: date, end: date) -> dict:
    """Map of ISO date -> holiday name for every holiday in [start, end]."""
    return {iso: h["name"] for iso, h in detail(conn, settings, start, end).items()}
