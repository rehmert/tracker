"""Release 668: calendar ordering is per-day time then compound."""
from datetime import date

from app.routers.calendar import calendar_day_sort_key, reconcile, calendar_review_items


def test_668_day_calendar_time_then_compound_and_missing_times_last():
    day = date(2026, 11, 19)
    planned = {day: [
        {"compound_id": 4, "name": "Zeta", "dose_time": "21:00", "protocol": "Evening"},
        {"compound_id": 2, "name": "beta", "dose_time": "08:00", "protocol": "Morning"},
        {"compound_id": 1, "name": "Alpha", "dose_time": "08:00", "protocol": "Morning"},
        {"compound_id": 3, "name": "No time", "dose_time": "", "protocol": "Morning"},
    ]}
    result = reconcile(planned, {}, day)
    assert [e["name"] for e in result[day]] == ["Alpha", "beta", "Zeta", "No time"]
    assert [e["status"] for e in result[day]] == ["due"] * 4


def test_668_unmatched_recording_in_same_day_order():
    day = date(2026, 11, 19)
    actual = {day: [
        {"compound_id": 3, "name": "Zinc", "dose_time": "09:00", "dose": "1 mg"},
        {"compound_id": 4, "name": "alpha", "dose_time": "07:30", "dose": "1 mg"},
    ]}
    events = reconcile({}, actual, day)[day]
    assert [e["name"] for e in events] == ["alpha", "Zinc"]
    assert all(e["status"] == "extra" for e in events)


def test_668_review_list_keeps_date_then_time_then_name():
    day = date(2026, 11, 19)
    events = reconcile({day: [
        {"compound_id": 1, "name": "Beta", "dose_time": "10:00"},
        {"compound_id": 2, "name": "Alpha", "dose_time": "10:00"},
    ]}, {}, day)
    items = calendar_review_items([{"date": day, "in_month": True, "events": events[day]}])
    assert [item["event"]["name"] for item in items] == ["Alpha", "Beta"]


def test_668_invalid_or_missing_clock_sorts_last():
    rows = [
        {"name": "untimed"},
        {"name": "late", "dose_time": "22:00"},
        {"name": "invalid", "dose_time": "not a time"},
    ]
    assert [r["name"] for r in sorted(rows, key=calendar_day_sort_key)] == [
        "late", "invalid", "untimed"
    ]
