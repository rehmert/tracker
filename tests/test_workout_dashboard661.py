"""Release 661: read-only dashboard Workout frequency and recent session regressions."""
from datetime import date, datetime, time, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal
from app.main import app
from app.workout_dashboard661 import workout_dashboard661
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 16)


def workout_at(db: Session, days_ago: int, hour: int, machines, *, completed=True):
    started = datetime.combine(TODAY - timedelta(days=days_ago), time(hour, 0))
    item = WorkoutSession654(
        started_at=started,
        completed_at=started + timedelta(hours=1) if completed else None,
    )
    db.add(item)
    db.flush()
    for equipment, pounds, reps in machines:
        db.add(WorkoutSet654(
            session_id=item.id, equipment_id=equipment,
            weight_lb=pounds, reps=reps, performed_at=started,
        ))
    return item


def test_661_rolling_calendar_frequency_and_backdated_order(tmp_path):
    """Isolated SQL fixture, no live database or prior active sessions."""
    eng = create_engine("sqlite:///" + str(tmp_path / "workouts661.db"))
    try:
        Base.metadata.create_all(eng, tables=[
            WorkoutEquipment654.__table__,
            WorkoutSession654.__table__,
            WorkoutSet654.__table__,
        ])
        with Session(eng) as db:
            first = WorkoutEquipment654(
                gym="661 QA", name="661 Chest", kind="selectorized",
            )
            second = WorkoutEquipment654(
                gym="661 QA", name="661 Row", kind="selectorized",
            )
            db.add_all([first, second])
            db.flush()

            # Insertion order intentionally differs from workout start order.
            morning = workout_at(db, 0, 9, [
                (first.id, 100, 10), (first.id, 105, 8), (second.id, 75, 12),
            ])
            six_days = workout_at(db, 6, 10, [(first.id, 95, 10)])
            afternoon = workout_at(db, 0, 15, [(second.id, 80, 8)])
            seven_days = workout_at(db, 7, 9, [(first.id, 100, 8)])
            twenty_eight = workout_at(db, 28, 9, [(first.id, 80, 10)])
            twenty_seven = workout_at(db, 27, 9, [(second.id, 65, 12)])
            ancient = workout_at(db, 35, 9, [(first.id, 60, 10)])
            unfinished = workout_at(
                db, 0, 13, [(first.id, 160, 10)], completed=False,
            )
            empty = workout_at(db, 0, 12, [])
            future = workout_at(db, -1, 8, [(first.id, 99, 7)])
            db.commit()

            before = db.scalar(select(func.count(WorkoutSession654.id)))
            result = workout_dashboard661(db, TODAY)
            after = db.scalar(select(func.count(WorkoutSession654.id)))
            assert before == after
            assert result["sessions7"] == 3
            assert result["days7"] == 2
            assert result["sessions28"] == 5
            assert result["days28"] == 4
            assert result["in_progress"] is True
            assert result["limit"] == 5
            recent_ids = [row.session_id for row in result["recent"]]
            assert recent_ids == [
                afternoon.id, morning.id, six_days.id,
                seven_days.id, twenty_seven.id,
            ]
            morning_view = next(row for row in result["recent"]
                                if row.session_id == morning.id)
            assert (morning_view.sets, morning_view.machines) == (3, 2)
            assert all(row.session_id not in recent_ids for row in
                       (twenty_eight, ancient, unfinished, empty, future))
            assert result["recent"][0].started_at == afternoon.started_at

            # Counted only completed sessions with sets, not set count.
            unfinished.completed_at = unfinished.started_at + timedelta(hours=1)
            db.flush()
            updated = workout_dashboard661(db, TODAY)
            assert updated["sessions7"] == 4
            assert updated["days7"] == 2
            assert updated["in_progress"] is False
    finally:
        eng.dispose()


def test_661_dashboard_http_readonly_quick_links_and_customization():
    with TestClient(app) as client:
        with SessionLocal() as db:
            equipment = WorkoutEquipment654(
                gym="661 QA", name="661 Testing " + uuid4().hex,
                kind="free_weight",
            )
            started = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
            # Ensure this test has a completed past workout even when
            # tests execute early in the morning.
            started -= timedelta(days=2)
            workout = WorkoutSession654(
                started_at=started, completed_at=started + timedelta(hours=1),
            )
            db.add_all([equipment, workout])
            db.flush()
            db.add(WorkoutSet654(
                session_id=workout.id, equipment_id=equipment.id,
                weight_lb=90, reps=10, performed_at=started,
            ))
            db.commit()
            sid = workout.id
            before = (
                db.scalar(select(func.count(WorkoutSession654.id))),
                db.scalar(select(func.count(WorkoutSet654.id))),
            )

        page = client.get("/")
        assert page.status_code == 200
        html = page.text
        assert html.count('data-dashboard-panel="9"') == 1
        assert 'data-dashboard-title="Workout activity"' in html
        assert 'id="tracker-workout-dashboard661"' in html
        assert "Workout Activity" in html
        assert "Training days · last 7 days" in html
        assert "Sessions · last 28 days" in html
        assert "Recent Completed Workouts" in html
        assert f'href="/workouts/sessions/{sid}"' in html
        assert "1 set · 1 machine" in html
        assert 'href="/workouts/quick"' in html
        assert 'href="/workouts/analytics"' in html
        assert 'href="/workouts"' in html
        assert "tracker-workout-dashboard661.css?v=661" in html
        assert 'id="dashboard-customize"' in html

        with SessionLocal() as db:
            after = (
                db.scalar(select(func.count(WorkoutSession654.id))),
                db.scalar(select(func.count(WorkoutSet654.id))),
            )
        assert before == after


def test_661_dashboard_empty_state_and_source_contract(tmp_path):
    eng = create_engine("sqlite:///" + str(tmp_path / "empty661.db"))
    try:
        Base.metadata.create_all(eng, tables=[
            WorkoutEquipment654.__table__,
            WorkoutSession654.__table__,
            WorkoutSet654.__table__,
        ])
        with Session(eng) as db:
            empty = workout_dashboard661(db, TODAY)
            assert empty["sessions7"] == 0
            assert empty["days7"] == 0
            assert empty["sessions28"] == 0
            assert empty["days28"] == 0
            assert empty["recent"] == []
            assert empty["in_progress"] is False
    finally:
        eng.dispose()

    from jinja2 import Environment
    for name in ("dashboard.html", "_workout_dashboard661.html"):
        Environment().parse(
            (ROOT / "app/templates" / name).read_text(encoding="utf-8")
        )

    source = (ROOT / "app/workout_dashboard661.py").read_text(encoding="utf-8")
    for token in (
        "completed_at.is_not(None)", "completed_at.is_(None)",
        "WorkoutSet654.session_id == WorkoutSession654.id",
        "func.distinct(func.date(WorkoutSession654.started_at))",
        "RECENT_WORKOUT_LIMIT661 = 5", "RECENT_DAYS661 = 7",
        "LONG_DAYS661 = 28", ".limit(RECENT_WORKOUT_LIMIT661)",
        "WorkoutSession654.started_at.desc()",
    ):
        assert token in source
    for forbidden in (
        "db.add(", "db.commit(", "db.delete(", "DROP TABLE", "ALTER TABLE",
        "Base.metadata", "request.", "httpx", "urlopen(",
    ):
        assert forbidden not in source
    dashboard = (ROOT / "app/routers/dashboard.py").read_text()
    assert "from ..workout_dashboard661 import workout_dashboard661" in dashboard
    assert "workout_summary=workout_dashboard661(db, today_date)" in dashboard
    html = (ROOT / "app/templates/dashboard.html").read_text()
    assert "{% include '_workout_dashboard661.html' %}" in html
    assert (ROOT / "app/static/css/tracker-workout-dashboard661.css").is_file()
