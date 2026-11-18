"""Release 654 focused tests. No live DB, unrelated suites, or network."""
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db import engine
from app.main import app

ROOT = Path(__file__).resolve().parents[1]


def _post(client, path, data=None):
    return client.post(path, data=data or {}, follow_redirects=False)


def test_654_catalog_manual_equipment_free_weights_and_session_logging():
    with TestClient(app) as client:
        assert {
            "workout_equipment654", "workout_sessions654", "workout_sets654"
        } <= set(inspect(engine).get_table_names())

        page = client.get("/workouts")
        assert page.status_code == 200
        assert "Find a machine" not in page.text
        assert "Equipment &amp; Logging" in page.text

        created = _post(client, "/workouts/equipment", {
            "name": "Nautilus Chest Press", "kind": "selectorized",
            "manufacturer": "Nautilus", "seat_setting": "4",
            "qr_value": "https://example.invalid/nautilus/test-654",
        })
        assert created.status_code == 303
        assert created.headers["location"].startswith("/workouts?msg=")

        duplicate = _post(client, "/workouts/equipment", {
            "name": "Another Chest Press", "kind": "selectorized",
            "qr_value": "https://example.invalid/nautilus/test-654",
        })
        # Obsolete QR form input must be ignored, not stored or rejected.
        assert duplicate.status_code == 303
        assert duplicate.headers["location"].startswith("/workouts?msg=")

        home = client.get("/workouts").text
        assert "Nautilus Chest Press" in home
        assert "Setup: 4" in home

        from app.workout_models654 import WorkoutEquipment654
        from app.db import SessionLocal
        with SessionLocal() as db:
            machine = db.query(WorkoutEquipment654).filter(
                WorkoutEquipment654.name == "Nautilus Chest Press"
            ).one()
            machine_id = machine.id
            assert machine.qr_value is None
            assert db.query(WorkoutEquipment654).filter(
                WorkoutEquipment654.name == "Another Chest Press"
            ).one().qr_value is None

        assert client.get("/workouts/qr", params={
            "code": "https://example.invalid/nautilus/test-654"
        }).status_code == 404

        free = _post(client, "/workouts/equipment", {
            "name": "Dumbbell Curl", "kind": "free_weight", "gym": "Home"
        })
        assert free.status_code == 303

        assert _post(client, "/workouts/start").status_code == 303
        invalid = _post(client, "/workouts/sets", {
            "equipment_id": machine_id, "weight_lb": "-5", "reps": "10"
        })
        assert invalid.headers["location"].startswith("/workouts?err=")
        valid = _post(client, "/workouts/sets", {
            "equipment_id": machine_id, "weight_lb": "100", "reps": "12", "effort": "7"
        })
        assert valid.status_code == 303
        logged = client.get("/workouts").text
        assert "100.0 lb" in logged and "12" in logged
        assert "Dumbbell Curl" in logged

        from app.workout_models654 import WorkoutSession654
        with SessionLocal() as db:
            session_id = db.query(WorkoutSession654).order_by(
                WorkoutSession654.id.desc()
            ).first().id
        history = client.get(f"/workouts/sessions/{session_id}")
        assert history.status_code == 200
        assert "100.0 lb" in history.text
        assert "Nautilus Chest Press" in history.text

        finished = _post(client, "/workouts/finish")
        assert finished.status_code == 303
        late = _post(client, "/workouts/sets", {
            "equipment_id": machine_id, "weight_lb": "100", "reps": "10"
        })
        assert late.headers["location"].startswith("/workouts?err=")


def test_654_template_and_route_contract():
    from jinja2 import Environment

    for template_name in ("workouts654.html", "workout_history654.html"):
        Environment().parse(
            (ROOT / "app/templates" / template_name).read_text(encoding="utf-8")
        )
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    nav = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
    assert "app.include_router(workouts654.router)" in main
    assert "('/workouts','Workouts')" in nav
    assert "get_scoped_db390" in (
        ROOT / "app/routers/workouts654.py"
    ).read_text(encoding="utf-8")
    assert (ROOT / "app/static/css/tracker-workouts654.css").is_file()



def test_654_additive_schema_is_repeatable_without_mutating_existing_data(tmp_path):
    from sqlalchemy import create_engine, text
    from app.db import Base

    isolated = create_engine("sqlite:///" + str(tmp_path / "existing.db"))
    try:
        with isolated.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE legacy_canary (id INTEGER PRIMARY KEY, value TEXT)")
            conn.exec_driver_sql("INSERT INTO legacy_canary(id, value) VALUES (1, 'keep')")
        Base.metadata.create_all(isolated)
        assert {
            "legacy_canary", "workout_equipment654",
            "workout_sessions654", "workout_sets654"
        } <= set(inspect(isolated).get_table_names())
        Base.metadata.create_all(isolated)
        with isolated.connect() as conn:
            assert conn.execute(text("SELECT value FROM legacy_canary WHERE id=1")).scalar_one() == "keep"
    finally:
        isolated.dispose()



def test_654_dev_missing_upload_policy_is_exactly_scoped():
    """Missing DEV uploads do not block releases, PROD still rejects them.

    Check behavior and branches, not a brittle count of shell condition strings.
    """
    runner = (ROOT / "scripts/tracker-release.sh").read_text(encoding="utf-8")
    assert '=== LIVE ATTACHMENT INTEGRITY BEFORE QUALIFICATION ===' in runner
    assert '=== LIVE ATTACHMENT INTEGRITY BEFORE MIGRATION BACKUP ===' in runner
    assert runner.count('if [[ "$INSTANCE" == DEV ]]; then') >= 2
    assert 'tracker-dev-attachment-gate650.py" --data "$LIVE_DATA_DIR"' in runner
    assert 'LIVE_ATTACHMENT_PREFLIGHT=DEV_ONLY_MISSING_POLICY' in runner
    assert 'LIVE_ATTACHMENT_PREBACKUP=DEV_MISSING_REFERENCES_NONBLOCKING' in runner
    assert '"$QA/scripts/tracker-workout-dev-backup655.py"' in runner
    assert 'DEV_MISSING_UPLOADS=NONBLOCKING' in runner
    assert 'tracker-attachment-integrity645.py" --data "$LIVE_DATA_DIR" --hashes' in runner
    assert '"$QA/scripts/tracker-restore-verify.py" --archive "$ARCHIVE"' in runner
    assert 'if [[ "$INSTANCE" == DEV ]]; then' in runner
    # PROD's preflight/prebackup checks and regular restore remain strict.
    assert 'PROD remains strict for every release' in runner
    assert 'from app.backup import create_backup' in runner

    historical = (ROOT / "scripts/tracker-coa-dev-backup652.py").read_text(
        encoding="utf-8"
    )
    assert "verify_dev_instance()" in historical
    assert "verify_archive(staged, missing)" in historical
