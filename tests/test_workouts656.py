"""Release 656: progress history, QR lookup and schema-free UI contracts."""
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from app.db import SessionLocal
from app.main import app
from app.workout_models654 import WorkoutEquipment654, WorkoutSet654
from app.routers.workouts656 import trend_points656

ROOT = Path(__file__).resolve().parents[1]


def post(client, path, data=None):
    return client.post(path, data=data or {}, follow_redirects=False)


def machine_id(name):
    with SessionLocal() as db:
        return db.scalar(
            select(WorkoutEquipment654.id)
            .where(WorkoutEquipment654.name == name)
            .order_by(WorkoutEquipment654.id.desc())
            .limit(1)
        )


def test_656_per_machine_progress_and_qr_scanning_lookup():
    with TestClient(app) as client:
        created = post(client, "/workouts/equipment", {
            "name": "Nautilus Progress Press 656",
            "kind": "selectorized",
            "gym": "Merritt Eldersburg",
            "qr_value": "https://example.invalid/nautilus?machine=656&unit=1",
        })
        assert created.status_code == 303
        equipment_id = machine_id("Nautilus Progress Press 656")
        assert equipment_id

        empty = client.get(f"/workouts/equipment/{equipment_id}/progress")
        assert empty.status_code == 200
        assert "No recorded sets yet" in empty.text
        assert "Session Load Trend" not in empty.text

        root = client.get("/workouts")
        assert root.status_code == 200
        assert 'data-start656' in root.text
        assert 'data-stop656' in root.text
        assert 'name="code"' in root.text  # manual fallback retained
        assert "View Machine Progress &amp; History" in root.text

        lookup = client.get("/workouts/qr", params={
            "code": "https://example.invalid/nautilus?machine=656&unit=1",
        }, follow_redirects=False)
        assert lookup.status_code == 303
        assert f"machine={equipment_id}" in lookup.headers["location"]

        assert post(client, "/workouts/start").status_code == 303
        for weight, reps in ((80, 12), (100, 8)):
            assert post(client, "/workouts/sets", {
                "equipment_id": equipment_id,
                "weight_lb": str(weight), "reps": str(reps),
            }).status_code == 303
        assert post(client, "/workouts/finish").status_code == 303

        assert post(client, "/workouts/start").status_code == 303
        assert post(client, "/workouts/sets", {
            "equipment_id": equipment_id, "weight_lb": "105", "reps": "5",
        }).status_code == 303
        assert post(client, "/workouts/finish").status_code == 303

        page = client.get(f"/workouts/equipment/{equipment_id}/progress")
        assert page.status_code == 200
        assert "Nautilus Progress Press 656 — Progress" in page.text
        assert "3" in page.text and "Sets recorded" in page.text
        assert "105.0 lb" in page.text
        assert "100.0 lb" in page.text
        assert "80.0 lb" in page.text
        assert 'aria-label="Heaviest recorded load per session' in page.text
        assert "<polyline points=" in page.text
        assert "estimated strength values" in page.text

        # Report generation must not modify workouts or sets.
        with SessionLocal() as db:
            count = len(list(db.scalars(select(WorkoutSet654).where(
                WorkoutSet654.equipment_id == equipment_id
            ))))
            assert count == 3
        assert client.get("/workouts/equipment/99999999/progress").status_code == 404


def test_656_progress_isolated_to_machine_and_escapes_unsafe_names():
    with TestClient(app) as client:
        other = post(client, "/workouts/equipment", {
            "name": "656 <script>alert(1)</script>",
            "kind": "free_weight",
        })
        assert other.status_code == 303
        equipment_id = machine_id("656 <script>alert(1)</script>")
        assert equipment_id
        view = client.get(f"/workouts/equipment/{equipment_id}/progress")
        assert view.status_code == 200
        assert "&lt;script&gt;" in view.text
        assert "<script>alert(1)</script>" not in view.text
        assert "No recorded sets yet" in view.text


def test_656_trend_points_are_bounded_and_deterministic():
    assert trend_points656([]) == ""
    assert trend_points656([120]) == ""
    assert trend_points656([100, 100]) == "28.0,89.0 672.0,89.0"
    assert trend_points656([80, 105]) == "28.0,138.0 672.0,40.0"
    assert trend_points656([105, 80]) == "28.0,40.0 672.0,138.0"


def test_656_ui_and_read_only_contracts():
    from jinja2 import Environment

    for name in ("workout_progress656.html", "workouts654.html"):
        Environment().parse(
            (ROOT / "app/templates" / name).read_text(encoding="utf-8")
        )
    main = (ROOT / "app/main.py").read_text()
    assert "app.include_router(workouts656.router)" in main
    route = (ROOT / "app/routers/workouts656.py").read_text()
    assert "get_scoped_db390" in route
    assert '@router.get("/workouts/equipment/{equipment_id}/progress")' in route
    assert "db.commit()" not in route
    assert "db.add(" not in route
    assert "db.delete(" not in route
    js = (ROOT / "app/static/js/tracker-workouts656.js").read_text()
    assert "getUserMedia" in js
    assert "BarcodeDetector" in js
    assert 'window.location.assign("/workouts/qr?code=" + encodeURIComponent(raw))' in js
    assert "window.open(" not in js
    assert "fetch(" not in js
