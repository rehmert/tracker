"""Release 666: routine-item target read context never changes workout logging."""
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from jinja2 import Environment
from sqlalchemy import func, select

from app.db import SessionLocal
from app.main import app
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655

ROOT = Path(__file__).resolve().parents[1]


def post666(client, path, data=None):
    return client.post(path, data=data or {}, follow_redirects=False)


def test_666_routine_item_is_scoped_to_active_routine_and_selected_machine():
    nonce = uuid4().hex[:10]
    with TestClient(app) as client:
        with SessionLocal() as db:
            a = WorkoutEquipment654(name="666 Press " + nonce, gym="QA", kind="selectorized")
            b = WorkoutEquipment654(name="666 Row " + nonce, gym="QA", kind="selectorized")
            outside = WorkoutEquipment654(name="666 Other " + nonce, gym="QA", kind="free_weight")
            routine = WorkoutRoutine655(name="666 Upper " + nonce)
            db.add_all([a, b, outside, routine])
            db.flush()
            item_a = WorkoutRoutineItem655(
                routine_id=routine.id, equipment_id=a.id, position=0,
            )
            item_b = WorkoutRoutineItem655(
                routine_id=routine.id, equipment_id=b.id, position=1,
            )
            db.add_all([item_a, item_b])
            db.commit()
            aid, bid, oid, rid = a.id, b.id, outside.id, routine.id
            ia, ib = item_a.id, item_b.id

        before = client.get(f"/workouts/quick?machine={aid}")
        assert before.status_code == 200
        assert 'id="workout666-targets"' not in before.text

        started = post666(client, f"/workouts/quick/routines/{rid}/start")
        assert started.status_code == 303
        assert started.headers["location"].startswith("/workouts/quick?machine=")

        first = client.get(f"/workouts/quick?machine={aid}")
        assert first.status_code == 200
        assert f'data-routine-id666="{rid}"' in first.text
        assert f'data-item-id666="{ia}"' in first.text
        assert f'data-item-id666="{ib}"' not in first.text
        assert "Browser-only intentions, not logged sets" in first.text
        assert "tracker-workout-targets666.js?v=666" in first.text
        assert f'href="/workouts/routines/{rid}/plan"' in first.text

        second = client.get(f"/workouts/quick?machine={bid}")
        assert second.status_code == 200
        assert f'data-item-id666="{ib}"' in second.text
        assert f'data-item-id666="{ia}"' not in second.text
        unrelated = client.get(f"/workouts/quick?machine={oid}")
        assert unrelated.status_code == 200
        assert 'id="workout666-targets"' not in unrelated.text

        with SessionLocal() as db:
            active_id = db.scalar(select(WorkoutSession654.id).where(
                WorkoutSession654.completed_at.is_(None)
            ).order_by(WorkoutSession654.id.desc()).limit(1))
            assert active_id
            assert db.scalar(select(func.count(WorkoutSet654.id)).where(
                WorkoutSet654.session_id == active_id
            )) == 0

        logged = post666(client, "/workouts/quick/sets", {
            "equipment_id": aid, "weight_lb": "95.5",
            "reps": "10", "effort": "7",
        })
        assert logged.status_code == 303
        with SessionLocal() as db:
            recorded = list(db.scalars(select(WorkoutSet654).where(
                WorkoutSet654.session_id == active_id
            )))
            assert len(recorded) == 1
            assert recorded[0].equipment_id == aid
            assert recorded[0].weight_lb == 95.5
            assert recorded[0].reps == 10
            assert recorded[0].effort == 7
        after_log = client.get(f"/workouts/quick?machine={aid}")
        assert after_log.status_code == 200
        assert 'action="/workouts/quick/sets"' in after_log.text
        assert 'name="weight_lb"' in after_log.text
        assert 'name="reps"' in after_log.text
        assert 'action="/workouts/quick/finish"' in after_log.text
        assert 'formaction="/workouts/finish-review"' in after_log.text
        assert 'value="95.5"' in after_log.text

        finished = post666(client, "/workouts/quick/finish")
        assert finished.status_code == 303
        assert 'id="workout666-targets"' not in client.get(
            f"/workouts/quick?machine={aid}"
        ).text


def test_666_source_contract_browser_only_read_and_jinja_safety():
    template = (ROOT / "app/templates/workout_quick659.html").read_text(
        encoding="utf-8"
    )
    route = (ROOT / "app/routers/workouts659.py").read_text(
        encoding="utf-8"
    )
    script = (ROOT / "app/static/js/tracker-workout-targets666.js").read_text(
        encoding="utf-8"
    )
    css = (ROOT / "app/static/css/tracker-workout-targets666.css").read_text(
        encoding="utf-8"
    )
    Environment().parse(template)
    for expected in (
        "{% if routine and plan_item_id %}",
        'data-routine-id666="{{ routine.id }}"',
        'data-item-id666="{{ plan_item_id }}"',
        'id="workout666-targets"',
        'id="workout666-target-values"',
        'data-target666="sets"',
        'data-target666="reps"',
        'data-target666="weight"',
        'action="/workouts/quick/sets"',
        'action="/workouts/quick/repeat"',
        'action="/workouts/quick/finish"',
        'formaction="/workouts/finish-review"',
    ):
        assert expected in template
    assert "if chosen and item.equipment_id == chosen.id" in route
    assert "plan_item_id=plan_item_id" in route
    for expected in (
        "tracker.workout665.plan.routine.",
        "localStorage.getItem",
        "JSON.parse",
        "payload.version !== 1",
        "Number.isFinite",
        "Number.isInteger",
        "textContent",
        'list.hidden = true',
        'list.hidden = false',
    ):
        assert expected in script
    for forbidden in (
        "localStorage.setItem", "localStorage.removeItem", "fetch(",
        "XMLHttpRequest", "sendBeacon(", "WebSocket", "FormData(",
        "document.cookie", "innerHTML", "requestSubmit(", ".submit(",
    ):
        assert forbidden not in script
    assert ".workout666-target-values[hidden]{display:none;}" in css
