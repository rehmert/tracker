"""Release 513: food date boundaries and safe iCalendar text.

These tests use an in-memory SQLite engine and synthetic calendar events.
They never touch an installed DEV or PROD database.
"""

from datetime import date

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.routers import (
    calendar as calendar_router,
    food,
    food_bundle376,
    food_quick375,
    food_week379,
)


@pytest.fixture
def isolated_food(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(food, "engine", engine)
    monkeypatch.setattr(food_quick375, "engine", engine)
    app = FastAPI()
    app.include_router(food.router)
    app.include_router(food_week379.router)
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


@pytest.mark.parametrize("invalid", [
    "0001-01-01", "0001-01-02", "0001-01-06", "9999-12-31",
])
def test_513_weekly_food_dates_fail_closed_before_data_access(invalid):
    with pytest.raises(HTTPException) as exc:
        food_quick375.selected_day(invalid)
    assert exc.value.status_code == 422

    with pytest.raises(HTTPException) as exc:
        food.food_page(None, day=invalid, db_engine=object())
    assert exc.value.status_code == 422

    with pytest.raises(HTTPException) as exc:
        food_bundle376.weekly_summary(invalid, db_engine=object())
    assert exc.value.status_code == 422

    with pytest.raises(HTTPException) as exc:
        food_week379.week_details(invalid, db_engine=object())
    assert exc.value.status_code == 422


@pytest.mark.parametrize("valid", ["0001-01-07", "2026-11-08", "9999-12-30"])
def test_513_food_date_limits_accept_full_calendar_window(valid):
    assert food_quick375.selected_day(valid) == valid
    assert food.require_supported_food_day(date.fromisoformat(valid)).isoformat() == valid


def test_513_food_routes_reject_early_dates_without_entries(isolated_food):
    client, engine = isolated_food
    assert client.get("/food?day=0001-01-06").status_code == 422
    assert client.get("/food/weekly.csv?day=0001-01-06").status_code == 422
    result = client.post(
        "/food/entry",
        data={
            "day": "0001-01-06",
            "name": "Reject out-of-range food",
            "servings": "1",
            "meal": "Breakfast",
            "energy": "100",
        },
        follow_redirects=False,
    )
    assert result.status_code == 422
    food.init_food_schema(engine)
    with engine.connect() as db:
        assert db.execute(text("SELECT COUNT(*) FROM tracker_food_entries")).scalar_one() == 0


def test_513_food_weekly_csv_at_earliest_supported_date(isolated_food):
    client, _ = isolated_food
    response = client.get("/food/weekly.csv?day=0001-01-07")
    assert response.status_code == 200
    assert "0001-01-01" in response.text
    assert "0001-01-07" in response.text


@pytest.mark.parametrize(("raw", "escaped"), [
    ("a\\b", "a\\\\b"),
    ("First\r\nSecond", "First\\nSecond"),
    ("First\rSecond", "First\\nSecond"),
    ("First\nSecond", "First\\nSecond"),
    ("A,B;C", "A\\,B\\;C"),
])
def test_513_calendar_ical_escape_normalizes_newlines(raw, escaped):
    assert calendar_router._ical_escape(raw) == escaped


def test_513_calendar_ics_cannot_inject_calendar_lines(monkeypatch):
    def fake_month_events(shown, db):
        return (
            date(2026, 11, 1),
            date(2026, 12, 1),
            {
                date(2026, 11, 5): [{
                    "name": "Alpha\r\nATTENDEE:injected@example.invalid",
                    "dose": "2 mg",
                    "status": "due",
                    "protocol": "Protocol\rBEGIN:VEVENT\nEND:VCALENDAR",
                    "dose_time": "08:00",
                    "fasting_hours": None,
                }]
            },
            [],
        )

    monkeypatch.setattr(calendar_router, "_month_events", fake_month_events)
    response = calendar_router.export_calendar_ics(month="2026-11", db=object())
    assert response.status_code == 200
    payload = response.body.decode("utf-8")
    physical = payload.split("\r\n")
    assert payload.endswith("\r\n")
    assert physical.count("BEGIN:VEVENT") == 1
    assert physical.count("END:VEVENT") == 1
    assert physical.count("END:VCALENDAR") == 1
    assert not any(line.startswith("ATTENDEE:") for line in physical)
    assert "Alpha\\nATTENDEE:" in payload
    assert "Protocol\\nBEGIN:VEVENT" in payload
    assert all(len(line.encode("utf-8")) <= 75 for line in physical)
