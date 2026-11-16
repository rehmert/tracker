"""Release 664: completed-only workout calendar boundaries, SQL and HTTP links."""
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jinja2 import Environment
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal
from app.main import app
from app.routers.workouts664 import (
    neighboring_month664, selected_month664, workout_calendar_data664,
)
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654

ROOT = Path(__file__).resolve().parents[1]
TODAY664 = date(2026, 11, 16)


def add_workout664(db, machine_id, started, weights, *, completed=True):
    session = WorkoutSession654(
        started_at=started,
        completed_at=started + timedelta(hours=1) if completed else None,
    )
    db.add(session)
    db.flush()
    for weight, reps in weights:
        db.add(WorkoutSet654(
            session_id=session.id, equipment_id=machine_id,
            weight_lb=weight, reps=reps, performed_at=started,
        ))
    return session


def test_664_leap_year_backdated_order_boundaries_and_unique_days(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "calendar664.db"))
    try:
        Base.metadata.create_all(engine, tables=[
            WorkoutEquipment654.__table__,
            WorkoutSession654.__table__,
            WorkoutSet654.__table__,
        ])
        with Session(engine) as db:
            machine = WorkoutEquipment654(
                name="664 machine", gym="QA", kind="selectorized",
            )
            db.add(machine)
            db.flush()

            # Insert in nonchronological order to prove backfill sorting.
            feb_early = add_workout664(
                db, machine.id, datetime(2024, 2, 1, 9), [(50, 10)],
            )
            leap_early = add_workout664(
                db, machine.id, datetime(2024, 2, 29, 8),
                [(75, 8), (70, 10)],
            )
            leap_late = add_workout664(
                db, machine.id, datetime(2024, 2, 29, 18), [(80, 6)],
            )
            before = add_workout664(
                db, machine.id, datetime(2024, 1, 31, 23), [(55, 7)],
            )
            after = add_workout664(
                db, machine.id, datetime(2024, 3, 1, 0), [(60, 8)],
            )
            unfinished = add_workout664(
                db, machine.id, datetime(2024, 2, 15, 9),
                [(95, 12)], completed=False,
            )
            empty = add_workout664(
                db, machine.id, datetime(2024, 2, 20, 9), [],
            )
            future = add_workout664(
                db, machine.id, datetime(2027, 1, 2, 9), [(70, 10)],
            )
            db.commit()

            before_count = db.scalar(select(func.count(WorkoutSet654.id)))
            summary = workout_calendar_data664(
                db, date(2024, 2, 1), TODAY664,
            )
            assert db.scalar(select(func.count(WorkoutSet654.id))) == before_count
            assert summary["month_label"] == "February 2024"
            assert summary["sessions"] == 3
            assert summary["training_days"] == 2
            assert summary["sets"] == 4
            assert summary["previous"] == "2024-01"
            assert summary["next"] == "2024-03"
            assert len(summary["weeks"]) in (4, 5, 6)
            assert all(len(week) == 7 for week in summary["weeks"])
            leap = next(cell for week in summary["weeks"] for cell in week
                        if cell["day"] == date(2024, 2, 29))
            assert leap["in_month"] and leap["count"] == 2
            assert sum(cell["count"] for week in summary["weeks"]
                       for cell in week if cell["in_month"]) == 3
            assert all(cell["count"] == 0 for week in summary["weeks"]
                       for cell in week if not cell["in_month"])

            assert [day["day"] for day in summary["days"]] == [
                date(2024, 2, 29), date(2024, 2, 1),
            ]
            assert [row.session_id for row in summary["days"][0]["sessions"]] == [
                leap_late.id, leap_early.id,
            ]
            assert summary["days"][0]["sets"] == 3
            assert summary["days"][1]["sessions"][0].session_id == feb_early.id
            excluded = {before.id, after.id, unfinished.id, empty.id, future.id}
            visible = {row.session_id for day in summary["days"]
                       for row in day["sessions"]}
            assert not visible.intersection(excluded)

            # Future-dated completed workouts never become historical sessions.
            future_summary = workout_calendar_data664(
                db, date(2027, 1, 1), TODAY664,
            )
            assert future_summary["sessions"] == 0
            assert future_summary["training_days"] == 0
            assert future_summary["sets"] == 0
    finally:
        engine.dispose()


def test_664_month_parser_rollovers_and_strict_invalid_query():
    today = date(2026, 11, 16)
    assert selected_month664(None, today) == date(2026, 11, 1)
    assert selected_month664("2024-02", today) == date(2024, 2, 1)
    assert neighboring_month664(date(2025, 12, 1), 1) == "2026-01"
    assert neighboring_month664(date(2025, 1, 1), -1) == "2024-12"
    assert neighboring_month664(date(1900, 1, 1), -1) is None
    assert neighboring_month664(date(2100, 12, 1), 1) is None

    for invalid in (
        "", "2026-2", "2026-00", "2026-13", "2026-11-01",
        "2026-11garbage", "20ab-01", "../2026-11", "0000-01",
        "1899-12", "2101-01", "2026-11%00",
    ):
        with pytest.raises(HTTPException) as exc:
            selected_month664(invalid, today)
        assert exc.value.status_code == 400


def test_664_http_calendar_links_and_no_get_writes():
    name = "664 Machine " + uuid4().hex
    with TestClient(app) as client:
        with SessionLocal() as db:
            machine = WorkoutEquipment654(
                name=name, gym="Calendar QA", kind="free_weight",
            )
            db.add(machine)
            db.flush()
            session = add_workout664(
                db, machine.id, datetime(2003, 4, 17, 9),
                [(85, 10), (95, 8)],
            )
            db.commit()
            sid = session.id
            before = (
                db.scalar(select(func.count(WorkoutSession654.id))),
                db.scalar(select(func.count(WorkoutSet654.id))),
            )

        response = client.get("/workouts/calendar?month=2003-04")
        assert response.status_code == 200
        html = response.text
        assert "Workout Calendar" in html
        assert "April 2003" in html
        assert 'href="/workouts/calendar?month=2003-03"' in html
        assert 'href="/workouts/calendar?month=2003-05"' in html
        assert 'data-date664="2003-04-17"' in html
        assert 'href="#workout664-day-2003-04-17"' in html
        assert 'id="workout664-day-2003-04-17"' in html
        assert f'href="/workouts/sessions/{sid}/review"' in html
        assert "2 recorded sets" in html
        assert "trainer" not in html.lower()

        default = client.get("/workouts/calendar")
        assert default.status_code == 200
        assert "Workout Calendar" in default.text
        assert 'href="/workouts/calendar"' in default.text
        for invalid in ("not-a-month", "2026-13", "2101-01"):
            assert client.get("/workouts/calendar", params={
                "month": invalid,
            }).status_code == 400
        workout_page = client.get("/workouts")
        assert workout_page.status_code == 200
        assert 'href="/workouts/calendar"' in workout_page.text
        overview = client.get("/")
        assert overview.status_code == 200
        assert 'href="/workouts/calendar"' in overview.text
        review = client.get(f"/workouts/sessions/{sid}/review")
        assert review.status_code == 200
        assert 'href="/workouts/calendar?month=2003-04"' in review.text

        with SessionLocal() as db:
            after = (
                db.scalar(select(func.count(WorkoutSession654.id))),
                db.scalar(select(func.count(WorkoutSet654.id))),
            )
        assert before == after


def test_664_empty_and_maximum_month_http():
    with TestClient(app) as client:
        empty = client.get("/workouts/calendar?month=2100-12")
        assert empty.status_code == 200
        assert "December 2100" in empty.text
        assert "No completed workouts with recorded sets in this month." in empty.text
        assert 'href="/workouts/calendar?month=2100-11"' in empty.text
        assert 'href="/workouts/calendar?month=2101-01"' not in empty.text


def test_664_source_safety_and_jinja_template():
    route = (ROOT / "app/routers/workouts664.py").read_text(encoding="utf-8")
    page = (ROOT / "app/templates/workout_calendar664.html").read_text(
        encoding="utf-8"
    )
    Environment().parse(page)
    for required in (
        "get_scoped_db390",
        '@router.get("/workouts/calendar")',
        "WorkoutSession654.completed_at.is_not(None)",
        "WorkoutSet654.session_id == WorkoutSession654.id",
        "WorkoutSession654.started_at >= start",
        "WorkoutSession654.started_at < upper",
        "func.count(WorkoutSet654.id)",
        "row.started_at.date()",
        "CALENDAR664.monthdatescalendar",
    ):
        assert required in route
    for forbidden in (
        "@router.post(", "db.add(", "db.delete(", "db.commit(",
        "Base.metadata", "DROP TABLE", "ALTER TABLE", "urlopen(",
        "httpx", "requests.",
    ):
        assert forbidden not in route
    for required in (
        "workout_calendar.sessions", "workout_calendar.training_days",
        "workout_calendar.sets", "workout_calendar.weeks",
        "workout_calendar.days", "workout664-day-",
        '/workouts/sessions/{{ item.session_id }}/review',
        "aria-current=\"date\"", "scope=\"col\"",
    ):
        assert required in page
    for forbidden in ("<form", "fetch(", "script src=", "POST"):
        assert forbidden not in page
