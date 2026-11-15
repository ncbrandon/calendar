import json
from collections import Counter
from datetime import date

from app import db, exporter, holidays, importer, sampling

TODAY = date(2026, 11, 14)


def add(conn, **kw):
    f = importer.clean(dict({"anchor_date": "2026-01-01"}, **kw))
    keys = list(f)
    conn.execute(f"INSERT INTO requirements ({','.join(keys)}) VALUES ({','.join('?' * len(keys))})", [f[k] for k in keys])


def tasks(conn):
    return [dict(r) for r in conn.execute(
        "SELECT t.*, r.name, r.cost FROM sample_tasks t JOIN requirements r ON r.id = t.requirement_id ORDER BY pull_date")]


def test_holidays():
    h = holidays.federal(2026)
    assert h[date(2026, 11, 26)] == "Thanksgiving Day"
    assert h[date(2026, 7, 3)] == "Independence Day (observed)"   # July 4, 2026 is a Saturday
    assert h[date(2026, 5, 25)] == "Memorial Day"


def test_periods():
    req = {"anchor_date": "2026-01-01", "end_date": None, "frequency": "triennial"}
    assert list(sampling.periods(req, TODAY, date(2029, 6, 1))) == [
        (date(2026, 1, 1), date(2028, 12, 31)), (date(2029, 1, 1), date(2031, 12, 31))]
    req["frequency"] = "quarterly"
    assert next(sampling.periods(req, TODAY, TODAY)) == (date(2026, 10, 1), date(2026, 12, 31))


def test_three_year_samples_are_spread_across_budget_years(conn):
    s = db.get_settings(conn)
    for i in range(9):
        add(conn, name=f"Group {i}", frequency="triennial", cost=300)
    sampling.ensure_tasks(conn, s, TODAY)
    current = [t for t in tasks(conn) if t["period_start"] == "2026-01-01"]
    assert len(current) == 9
    years = Counter(t["pull_date"][:4] for t in current)
    assert set(years) <= {"2026", "2027", "2028"}
    assert years["2027"] >= 3 and years["2028"] >= 3 and years["2026"] <= 1
    for t in current:
        pull, order = date.fromisoformat(t["pull_date"]), date.fromisoformat(t["order_date"])
        assert pull.weekday() in (0, 1, 2)                     # Mon-Wed
        assert pull <= date(2028, 6, 30)                       # six-month buffer before the deadline
        assert pull >= TODAY and (pull - order).days >= 14 and order.weekday() < 5
    months = Counter(t["pull_date"][:7] for t in current)
    assert max(months.values()) == 1                           # no two in the same month


def test_allowed_months_and_manual_moves_survive_a_rebalance(conn):
    s = db.get_settings(conn)
    add(conn, name="Lead and Copper", frequency="triennial", cost=450, allowed_months="6,7,8,9")
    add(conn, name="IOC", frequency="triennial", cost=300)
    sampling.ensure_tasks(conn, s, TODAY)
    lcr = next(t for t in tasks(conn) if t["name"] == "Lead and Copper" and t["period_start"] == "2026-01-01")
    assert int(lcr["pull_date"][5:7]) in (6, 7, 8, 9)
    ioc = next(t for t in tasks(conn) if t["name"] == "IOC" and t["period_start"] == "2026-01-01")
    sampling.move_task(conn, s, ioc["id"], date(2027, 3, 9), TODAY)
    sampling.rebalance(conn, s, TODAY)
    again = next(t for t in tasks(conn) if t["id"] == ioc["id"])
    assert again["pull_date"] == "2027-03-09" and again["locked"] == 1


def test_monthly_and_calendar_items_and_export(conn):
    s = db.get_settings(conn)
    add(conn, name="Coliform", frequency="monthly", samples_per_period=2, cost=22, lead_days=7)
    add(conn, name="Nitrate", frequency="annual", cost=35)
    sampling.ensure_tasks(conn, s, TODAY)
    dec = [t for t in tasks(conn) if t["name"] == "Coliform" and t["period_start"] == "2026-12-01"]
    assert len(dec) == 2 and dec[0]["pull_date"] != dec[1]["pull_date"]
    items = sampling.calendar_items(conn, date(2026, 12, 1), date(2026, 12, 31), TODAY)
    kinds = Counter(i["type"] for day in items.values() for i in day)
    assert kinds["pull"] >= 2 and kinds["order"] >= 2
    conn.execute("INSERT INTO events (title, date, category) VALUES ('Chlorine delivery', '2026-12-03', 'delivery')")
    md = exporter.markdown(conn, s, date(2026, 12, 1), date(2026, 12, 31), TODAY)
    assert "Chlorine delivery" in md and "Coliform" in md and "Christmas Day" in md and "## Pay weeks" in md
    assert sampling.budget(conn, s)["years"]


def test_spreadsheet_import():
    rows = importer.parse_table("x.csv", importer.TEMPLATE.encode())
    assert len(rows) == 6 and rows[0]["frequency"] == "triennial"
    assert json.loads(rows[0]["allowed_months"]) == [6, 7, 8, 9]
    assert importer.clean({"name": "X", "frequency": "Every 3 years"})["frequency"] == "triennial"


def test_multi_day_and_yearly_holidays(conn):
    settings = db.get_settings(conn)
    settings["holiday_extra"] = ["Day after Thanksgiving"]
    conn.execute("INSERT INTO holidays (date, end_date, name, yearly) VALUES ('2026-12-24', '2026-12-26', 'Holiday', 1)")
    got = holidays.between(conn, settings, date(2026, 11, 1), date(2027, 12, 31))
    assert got["2026-11-27"] == "Day after Thanksgiving"      # the Friday after the 4th Thursday
    assert got["2027-11-26"] == "Day after Thanksgiving"
    for iso in ("2026-12-24", "2026-12-25", "2026-12-26", "2027-12-24", "2027-12-26"):
        assert got[iso] == "Holiday"                           # your own entry wins over the federal name
    assert "2026-12-27" not in got and "2026-12-23" not in got
    one = holidays.detail(conn, settings, date(2026, 12, 24), date(2026, 12, 24))["2026-12-24"]
    assert one["id"] is not None
