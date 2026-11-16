"""Release 660 regression tests: actual completed-session machine analytics, no writes."""
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.main import app
from app.routers.workouts660 import chart_points660, range660
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654

ROOT = Path(__file__).resolve().parents[1]


def seed660():
    suffix = uuid4().hex
    with SessionLocal() as db:
        machine = WorkoutEquipment654(
            gym="Analytics QA", name="660 Progress " + suffix,
            kind="selectorized",
        )
        other = WorkoutEquipment654(
            gym="Analytics QA", name="660 Neighbor " + suffix,
            kind="free_weight",
        )
        empty = WorkoutEquipment654(
            gym="Analytics QA", name="660 Empty " + suffix,
            kind="bodyweight",
        )
        db.add_all([machine, other, empty])
        db.flush()
        ids = (machine.id, other.id, empty.id)
        workouts = [
            (datetime(2025, 5, 2, 9), [(100, 8), (80, 12)]),
            (datetime(2025, 5, 9, 9), [(110, 8), (90, 12)]),
            (datetime(2025, 5, 5, 9), [(105, 8), (80, 10)]),
        ]
        # Intentionally insert backdated workout after the newest date.
        sessions = []
        for started, actual in workouts:
            session = WorkoutSession654(
                started_at=started, completed_at=started.replace(hour=10),
            )
            db.add(session)
            db.flush()
            sessions.append(session.id)
            for pounds, reps in actual:
                db.add(WorkoutSet654(
                    session_id=session.id, equipment_id=machine.id,
                    weight_lb=pounds, reps=reps, performed_at=started,
                ))
        # Active session and unrelated exercise must NOT affect analytics.
        active = WorkoutSession654(started_at=datetime(2025, 6, 1, 9))
        unrelated = WorkoutSession654(
            started_at=datetime(2025, 5, 3, 9),
            completed_at=datetime(2025, 5, 3, 10),
        )
        db.add_all([active, unrelated])
        db.flush()
        db.add_all([
            WorkoutSet654(
                session_id=active.id, equipment_id=machine.id,
                weight_lb=1900, reps=200,
            ),
            WorkoutSet654(
                session_id=unrelated.id, equipment_id=other.id,
                weight_lb=400, reps=10,
            ),
        ])
        db.commit()
        return ids, sessions, active.id


def test_660_completed_actual_pr_volume_and_repmatched_trends():
    with TestClient(app) as client:
        (machine, other, empty), ids, active_id = seed660()
        page = client.get("/workouts/analytics", params={"machine": machine})
        assert page.status_code == 200
        text = page.text
        assert "Strength Progress" in text
        assert "Completed sessions" in text
        assert "Recorded sets" in text
        assert "Total repetitions" in text
        assert ">3</strong>" in text
        assert ">6</strong>" in text
        assert ">58</strong>" in text
        assert "5,360.0" in text   # 1760 + 1960 + 1640
        assert "110.0 lb" in text  # actual heaviest completed set
        assert "1,080.0 lb × reps" in text  # 90 × 12
        assert "1900.0 lb" not in text  # active-session outlier
        assert "400.0 lb" not in text  # other-machine outlier
        assert "8- rep" not in text
        assert "8-rep sets" in text
        assert "exactly 8 repetitions" in text
        assert text.count("<polyline") == 2
        for sid in ids:
            assert f"/workouts/sessions/{sid}" in text

        # Chronological trend must follow entered workout time, not ID.
        table = text.split(
            "<caption>Completed sessions on this machine (newest first)</caption>"
        )[1].split("</table>")[0]
        assert table.index(f"/workouts/sessions/{ids[1]}") < table.index(
            f"/workouts/sessions/{ids[2]}"
        ) < table.index(f"/workouts/sessions/{ids[0]}")

        different = client.get("/workouts/analytics", params={
            "machine": machine, "reps": 12,
        })
        assert different.status_code == 200
        assert "exactly 12 repetitions" in different.text
        assert "90.0 lb" in different.text
        assert "80.0 lb" in different.text
        assert "110.0 lb" in different.text  # other summary remains unchanged
        assert different.text.count("<polyline") == 2

        no_match = client.get("/workouts/analytics", params={
            "machine": machine, "reps": 5,
        })
        assert no_match.status_code == 200
        assert "No completed workout has an exactly 5-repetition set" in no_match.text

        other_page = client.get("/workouts/analytics", params={
            "machine": other,
        })
        assert other_page.status_code == 200
        assert "400.0 lb" in other_page.text
        assert "5,360.0" not in other_page.text
        empty_page = client.get("/workouts/analytics", params={"machine": empty})
        assert empty_page.status_code == 200
        assert "No completed-session sets yet" in empty_page.text
        assert "Recorded Personal Records" not in empty_page.text

        assert client.get("/workouts/analytics", params={
            "machine": 99999999,
        }).status_code == 404
        for value in ("0", "201", "-1", "oops"):
            assert client.get("/workouts/analytics", params={
                "machine": machine, "reps": value,
            }).status_code == 422

        with SessionLocal() as db:
            active = db.get(WorkoutSession654, active_id)
            assert active and active.completed_at is None
            count = db.scalar(select(func.count(WorkoutSet654.id)).where(
                WorkoutSet654.equipment_id == machine,
            ))
            assert count == 7  # six completed, one active
            # This fixture's unfinished workout must not contaminate
            # subsequent legacy Workout tests using the same isolated DB.
            db.execute(delete(WorkoutSet654).where(
                WorkoutSet654.session_id == active_id,
            ))
            db.execute(delete(WorkoutSession654).where(
                WorkoutSession654.id == active_id,
            ))
            db.commit()


def test_660_escapes_names_and_links_from_all_workout_entries():
    unsafe = "660 <img src=x onerror=alert(1)>"
    with TestClient(app) as client:
        with SessionLocal() as db:
            item = WorkoutEquipment654(
                gym="Analytics Test", name=unsafe, kind="selectorized",
            )
            db.add(item)
            db.commit()
            mid = item.id
        page = client.get("/workouts/analytics", params={"machine": mid})
        assert page.status_code == 200
        assert "&lt;img src=x onerror=alert(1)&gt;" in page.text
        assert "<img src=x onerror=alert(1)>" not in page.text
        home = client.get("/workouts")
        assert home.status_code == 200
        assert 'href="/workouts/analytics"' in home.text
        quick = client.get("/workouts/quick")
        assert 'href="/workouts/analytics"' in quick.text
        progress = client.get(f"/workouts/equipment/{mid}/progress")
        assert f'href="/workouts/analytics?machine={mid}"' in progress.text


def test_660_chart_coordinate_bounds_and_no_fake_1rm():
    assert chart_points660([]) == ""
    assert chart_points660([100]) == ""
    assert chart_points660([100, 100]) == "28.0,89.0 672.0,89.0"
    assert chart_points660([80, 105]) == "28.0,138.0 672.0,40.0"
    assert chart_points660([105, 80]) == "28.0,40.0 672.0,138.0"
    assert chart_points660([float("nan"), 100]) == ""
    assert range660([]) == (0.0, 0.0)
    assert range660([80, 105, 92]) == (80, 105)

    from jinja2 import Environment
    for page in (
        "workout_analytics660.html", "workouts654.html",
        "workout_progress656.html", "workout_quick659.html",
    ):
        Environment().parse(
            (ROOT / "app/templates" / page).read_text(encoding="utf-8")
        )
    source = (ROOT / "app/routers/workouts660.py").read_text(
        encoding="utf-8"
    )
    for token in (
        "get_scoped_db390", "completed_at.is_not(None)",
        "MAX_SESSION_POINTS660 = 20", "MAX_REP_CHOICES660 = 12",
        "WorkoutSet654.reps == reps_selected",
        "WorkoutSet654.equipment_id == selected.id",
    ):
        assert token in source
    for forbidden in (
        "db.add(", "db.delete(", "db.commit(", "Base.metadata",
        "@router.post(", "ALTER TABLE", "httpx", "urlopen(",
    ):
        assert forbidden not in source
    assert "app.include_router(workouts660.router)" in (
        ROOT / "app/main.py"
    ).read_text(encoding="utf-8")
