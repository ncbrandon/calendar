from datetime import date, timedelta

from app import db, rotation

THU = date(2026, 11, 12)  # a Thursday


def ids(conn):
    return {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM employees")}


def who(conn, day):
    settings = db.get_settings(conn)
    names = {v: k for k, v in ids(conn).items()}
    return names.get(rotation.oncall_between(conn, settings, day, day)[day.isoformat()]["employee_id"])


def test_unassigned_until_someone_is_picked(conn):
    assert who(conn, THU) is None


def test_thursday_pick_fills_through_wednesday_then_alternates(conn):
    s = db.get_settings(conn)
    rotation.set_oncall(conn, s, THU, ids(conn)["Jody"])
    for i in range(7):                                   # Thu 12th .. Wed 18th
        assert who(conn, THU + timedelta(days=i)) == "Jody"
    for i in range(7, 14):                               # next Thu .. Wed
        assert who(conn, THU + timedelta(days=i)) == "Marcus"
    assert who(conn, THU + timedelta(days=14)) == "Jody"
    assert who(conn, THU + timedelta(days=7 * 51)) == "Marcus"
    assert who(conn, THU - timedelta(days=1)) is None    # nothing before the first pick


def test_brandon_covers_a_week_without_shifting_the_rotation(conn):
    s = db.get_settings(conn)
    rotation.set_oncall(conn, s, THU, ids(conn)["Jody"])
    nxt = THU + timedelta(days=7)                        # Marcus's week
    rotation.set_oncall(conn, s, nxt, ids(conn)["Brandon"])
    assert all(who(conn, nxt + timedelta(days=i)) == "Brandon" for i in range(7))
    assert who(conn, nxt + timedelta(days=7)) == "Jody"  # rotation carried on underneath
    rotation.set_oncall(conn, s, nxt, None)              # Auto on Thursday clears the week
    assert who(conn, nxt + timedelta(days=3)) == "Marcus"


def test_single_day_swap(conn):
    s = db.get_settings(conn)
    rotation.set_oncall(conn, s, THU, ids(conn)["Jody"])
    sat = THU + timedelta(days=2)
    rotation.set_oncall(conn, s, sat, ids(conn)["Brandon"])
    assert who(conn, sat) == "Brandon"
    assert who(conn, sat + timedelta(days=1)) == "Jody"
    rotation.set_oncall(conn, s, sat, None)
    assert who(conn, sat) == "Jody"


def test_repicking_a_later_thursday_restarts_from_there_and_keeps_history(conn):
    s = db.get_settings(conn)
    rotation.set_oncall(conn, s, THU, ids(conn)["Jody"])
    later = THU + timedelta(days=14)                     # would be Jody
    rotation.set_oncall(conn, s, later, ids(conn)["Marcus"])
    assert who(conn, later) == "Marcus"
    assert who(conn, later + timedelta(days=7)) == "Jody"
    assert who(conn, THU) == "Jody" and who(conn, THU + timedelta(days=7)) == "Marcus"
