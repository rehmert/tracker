"""Release 662: Rapid Gym machine navigation and fast-entry UI regression."""
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.main import app
from app.workout_models654 import WorkoutEquipment654, WorkoutSet654
from app.workout_models655 import WorkoutRoutine655

ROOT = Path(__file__).resolve().parents[1]


def post(client, url, data=None):
    return client.post(url, data=data or {}, follow_redirects=False)


def create_machine662(client, name):
    response = post(client, "/workouts/equipment", {
        "name": name, "kind": "selectorized", "gym": "662 Gym",
    })
    assert response.status_code == 303
    with SessionLocal() as db:
        machine_id = db.scalar(
            select(WorkoutEquipment654.id).where(
                WorkoutEquipment654.name == name,
            ).order_by(WorkoutEquipment654.id.desc()).limit(1)
        )
    assert machine_id
    return machine_id


def test_662_routine_machine_search_and_fast_set_entry_no_new_writes():
    unique = uuid4().hex[:9]
    with TestClient(app) as client:
        first_name = "662 Press " + unique
        second_name = "662 Row " + unique
        first = create_machine662(client, first_name)
        second = create_machine662(client, second_name)
        routine_name = "662 Routine " + unique
        assert post(client, "/workouts/routines", {
            "name": routine_name,
        }).status_code == 303
        with SessionLocal() as db:
            routine = db.scalar(select(WorkoutRoutine655).where(
                WorkoutRoutine655.name == routine_name
            ))
            assert routine
            routine_id = routine.id
        for equipment_id in (first, second):
            assert post(client, f"/workouts/routines/{routine_id}/equipment", {
                "equipment_id": equipment_id,
            }).status_code == 303
        started = post(client, f"/workouts/quick/routines/{routine_id}/start")
        assert started.status_code == 303
        assert f"machine={first}" in started.headers["location"]

        with SessionLocal() as db:
            before = db.scalar(select(func.count(WorkoutSet654.id)))
        page = client.get(f"/workouts/quick?machine={first}")
        assert page.status_code == 200
        html = page.text
        assert 'href="/static/css/tracker-workout-gym-bundle745.css?v=745"' in html
        assert 'href="/static/css/tracker-workouts662.css' not in html
        assert 'src="/static/js/tracker-workouts662.js?v=662"' in html
        assert 'id="workout662-directory"' in html
        assert 'id="workout662-search"' in html
        assert 'id="workout662-results"' in html
        assert f'href="/workouts/quick?machine={first}"' in html
        assert f'href="/workouts/quick?machine={second}"' in html
        assert f'data-search662="{first_name} 662 Gym"' in html
        assert f'data-search662="{second_name} 662 Gym"' in html
        assert 'aria-current="page"' in html
        for delta in ('-2.5', '2.5', '-5', '5'):
            assert f'data-delta659="{delta}"' in html
        assert "Clear entries" in html
        assert "Next Machine: " + second_name in html
        assert "workout662-next" in html
        with SessionLocal() as db:
            assert db.scalar(select(func.count(WorkoutSet654.id))) == before

        # Old validated 659 write path remains the only recording endpoint.
        saved = post(client, "/workouts/quick/sets", {
            "equipment_id": first, "weight_lb": "102.5",
            "reps": "10", "effort": "8",
        })
        assert saved.status_code == 303
        assert "logged=1" in saved.headers["location"]
        updated = client.get(f"/workouts/quick?machine={first}")
        assert updated.status_code == 200
        assert 'value="102.5"' in updated.text
        assert 'value="10"' in updated.text
        assert "Restore last recorded values" in updated.text

        next_page = client.get(f"/workouts/quick?machine={second}")
        assert next_page.status_code == 200
        assert "← Previous: " + first_name in next_page.text
        assert f'data-search662="{second_name} 662 Gym"' in next_page.text
        assert post(client, "/workouts/quick/finish").status_code == 303


def test_662_untrusted_machine_text_is_escaped_and_existing_routes_unchanged():
    unique = uuid4().hex
    unsafe = "662 <svg onload=alert(1)> " + unique
    with TestClient(app) as client:
        mid = create_machine662(client, unsafe)
        assert post(client, "/workouts/quick/start").status_code == 303
        page = client.get(f"/workouts/quick?machine={mid}")
        assert page.status_code == 200
        assert "<svg onload=alert(1)>" not in page.text
        assert "&lt;svg onload=alert(1)&gt;" in page.text
        assert 'action="/workouts/quick/sets"' in page.text
        assert 'action="/workouts/quick/repeat"' not in page.text
        assert 'action="/workouts/quick/finish"' in page.text
        assert post(client, "/workouts/quick/finish").status_code == 303


def test_662_template_and_assets_no_mutation_contract():
    from jinja2 import Environment

    page = (ROOT / "app/templates/workout_quick659.html").read_text()
    Environment().parse(page)
    assert page.count('id="workout662-directory"') == 1
    assert page.count('id="workout662-search"') == 1
    assert page.count('data-search662=') == 1
    assert page.count('class="workout662-nav"') == 1
    assert page.count('type="reset" class="workout662-restore"') == 1
    assert 'data-step659="weight" data-delta659="2.5"' in page
    assert 'data-step659="reps" data-delta659="5"' in page
    assert 'action="/workouts/quick/sets"' in page

    # Existing 659 router, JS, data model and all POST endpoints are unchanged.
    script = (ROOT / "app/static/js/tracker-workouts662.js").read_text()
    for protected in (
        "fetch(", "XMLHttpRequest", "localStorage", "document.cookie",
        "eval(", "new Function", "innerHTML",
    ):
        assert protected not in script
    assert "picker.requestSubmit()" in script
    assert 'search.addEventListener("input", refresh)' in script
    assert ".workout662-directory-list a[data-search662]" in script
    css = (ROOT / "app/static/css/tracker-workouts659.css").read_text()
    assert 'a[hidden]' in css
