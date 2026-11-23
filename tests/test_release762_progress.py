"""Release 762 isolated progress dashboard regression suite.

All generated measurements are synthetic. The dashboard never needs a BIA
device, nor may it create records in existing vital/workout/lab tables.
"""
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import VitalReading, LabReport, LabResult
from app.food_read_engine406 import get_food_read_engine406
from app.progress_calc762 import (daily_weights762, moving762, weight_report762,
                                  strength_trend762, interpret762)
from app.progress_models762 import (ProgressMeasure762, ProgressComposition762,
                                    ProgressFunction762, ProgressMarker762)
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models667 import WorkoutSetType667

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def progress_client762():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    food = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with food.begin() as db:
        db.exec_driver_sql("CREATE TABLE tracker_food_products (id INTEGER PRIMARY KEY, nutrients TEXT)")
        db.exec_driver_sql("CREATE TABLE tracker_food_entries (id INTEGER PRIMARY KEY, product_id INTEGER, eaten_on TEXT, servings REAL)")
        db.exec_driver_sql("CREATE TABLE tracker_food_targets (nutrient TEXT PRIMARY KEY, value REAL)")

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_food_read_engine406] = lambda: food
    try:
        with TestClient(app) as client:
            yield client, engine, food
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_food_read_engine406, None)
        engine.dispose()
        food.dispose()


def test_762_weight_average_coverage_and_no_backfill():
    today = date.today()
    rows = [SimpleNamespace(id=i+1, measured_at=datetime.combine(today-timedelta(days=6-i), datetime.min.time()),
                            weight_kg=100-i) for i in range(7)]
    observed = daily_weights762(rows)
    assert len(moving762(observed, 7, min_samples=3)) == 5
    report = weight_report762(observed, today, 105, 80)
    assert report["latest"] == 94
    assert report["lost"] == 11
    assert report["remaining"] == 14
    assert report["n7"] == 7
    assert report["d7"] is None
    assert report["d28"] is None
    assert report["plateau"] is None
    today2 = datetime.combine(today, datetime.min.time())
    rows.append(SimpleNamespace(id=100, measured_at=today2, weight_kg=93))
    assert daily_weights762(rows)[-1][1] == 93


def test_762_same_machine_same_reps_only():
    today = date.today()
    entries = [(today-timedelta(days=20), 1, 8, 100),
               (today-timedelta(days=10), 1, 10, 1000),
               (today-timedelta(days=5), 2, 8, 900),
               (today, 1, 8, 110)]
    points, verdict = strength_trend762(entries, 1, 8)
    assert len(points) == 2
    assert verdict == "Improving"
    assert strength_trend762(entries, 1, 12)[1] == "Not enough comparable sets"


def test_762_empty_dashboard_no_false_zero(progress_client762):
    client, _, _ = progress_client762
    response = client.get("/progress")
    assert response.status_code == 200, response.text[:250]
    assert "Progress Dashboard" in response.text
    assert "No tape measurements" in response.text
    assert "Insufficient data" in response.text
    assert "Optional body composition" in response.text
    assert "No days with protein values for every logged food item" in response.text
    assert 'href="/progress"' in client.get("/").text


def test_762_preferences_and_tape_macd_with_units(progress_client762):
    client, engine, _ = progress_client762
    today = date.today().isoformat()
    settings = client.post("/progress/settings", data={
        "height": "71", "height_unit": "in",
        "starting_weight": "325", "goal_weight": "215", "weight_unit": "lb",
        "measurement_unit": "in", "freq_weight": 1, "freq_waist": 7,
        "freq_other": 21, "freq_strength": 0, "freq_bia": 21,
        "freq_photos": 30, "freq_dexa": 150, "freq_labs": 0,
    }, follow_redirects=True)
    assert settings.status_code == 200, settings.text[:400]
    response = client.post("/progress/measure/save", data={
        "measured_on": today, "unit": "in", "waist_navel": "44.5",
        "hip": "46", "notes": "Measured at navel",
    }, follow_redirects=True)
    assert response.status_code == 200, response.text[:400]
    assert "44.5" in response.text
    with Session(engine) as db:
        row = db.scalar(select(ProgressMeasure762))
        assert row.waist_navel == pytest.approx(113.03)
        rid = row.id
    edit = client.get(f"/progress?edit_kind=measure&edit_id={rid}")
    assert edit.status_code == 200 and f'value="{rid}"' in edit.text
    response = client.post("/progress/measure/save", data={
        "record_id": str(rid), "measured_on": today, "unit": "cm",
        "waist_navel": "110.5",
    }, follow_redirects=True)
    assert response.status_code == 200
    with Session(engine) as db:
        assert db.get(ProgressMeasure762, rid).waist_navel == pytest.approx(110.5)
    response = client.post(f"/progress/measure/{rid}/delete", follow_redirects=True)
    assert response.status_code == 200
    with Session(engine) as db:
        assert db.get(ProgressMeasure762, rid) is None


def test_762_bia_and_dexa_distinct_methods(progress_client762):
    client, engine, _ = progress_client762
    day = date.today().isoformat()
    for method, pct in (("BIA", "28.3"), ("DEXA", "26.8")):
        resp = client.post("/progress/composition/save", data={
            "measured_on": day, "method": method, "mass_unit": "lb",
            "body_fat_pct": pct, "fat_free_mass_kg": "170",
            "device": "Synthetic instrument",
            "conditions": "Synthetic test",
        }, follow_redirects=True)
        assert resp.status_code == 200, resp.text[:400]
    page = client.get("/progress")
    assert "BIA body-fat estimate" in page.text
    assert "DEXA body-fat estimate" in page.text
    with Session(engine) as db:
        rows = list(db.scalars(select(ProgressComposition762)))
        assert {r.method for r in rows} == {"BIA", "DEXA"}
        assert all(r.fat_free_mass_kg == pytest.approx(77.1107, abs=0.005) for r in rows)


def test_762_function_and_intervention_macd(progress_client762):
    client, engine, _ = progress_client762
    day = date.today().isoformat()
    func = client.post("/progress/function/save", data={
        "measured_on": day, "knee_pain": "2", "walking_minutes": "30",
        "distance_unit": "mi", "walking_distance_km": "1.5",
        "notes": "Synthetic mobility",
    }, follow_redirects=True)
    assert func.status_code == 200
    with Session(engine) as db:
        record = db.scalar(select(ProgressFunction762))
        assert record.walking_distance_km == pytest.approx(2.414, abs=.005)
    marker = client.post("/progress/marker/save", data={
        "measured_on": day, "category": "workout", "label": "New routine",
    }, follow_redirects=True)
    assert marker.status_code == 200
    assert "New routine" in client.get("/progress?markers=1").text
    with Session(engine) as db:
        mid = db.scalar(select(ProgressMarker762)).id
    assert client.post(f"/progress/marker/{mid}/delete", follow_redirects=True).status_code == 200


def test_762_invalid_numbers_future_dates_and_wrong_ids(progress_client762):
    client, engine, _ = progress_client762
    day = date.today().isoformat()
    for value in ("NaN", "inf", "-50", "100000"):
        response = client.post("/progress/measure/save", data={
            "measured_on": day, "unit": "cm", "waist_navel": value,
        }, follow_redirects=True)
        assert response.status_code == 200
    with Session(engine) as db:
        assert not list(db.scalars(select(ProgressMeasure762)))
    response = client.post("/progress/measure/save", data={
        "measured_on": (date.today()+timedelta(days=1)).isoformat(),
        "unit": "cm", "waist_navel": "100",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert client.post("/progress/measure/987654/delete").status_code == 404
    assert client.post("/progress/other/save", data={"measured_on": day}).status_code == 404


def test_762_live_data_reuse_without_mutation(progress_client762):
    client, engine, food = progress_client762
    now = datetime.now().replace(microsecond=0)
    yesterday = now-timedelta(days=1)
    with Session(engine) as db:
        db.add_all([VitalReading(measured_at=now, weight_kg=105, systolic=112, diastolic=70, pulse_bpm=68),
                    VitalReading(measured_at=yesterday, weight_kg=106)])
        equipment = WorkoutEquipment654(gym="Synthetic", name="Synthetic Nautilus 762", kind="selectorized")
        db.add(equipment)
        db.flush()
        for offset, value in ((10, 90), (2, 100)):
            started = now-timedelta(days=offset)
            session = WorkoutSession654(started_at=started, completed_at=started+timedelta(minutes=30))
            db.add(session)
            db.flush()
            db.add(WorkoutSet654(session_id=session.id, equipment_id=equipment.id, weight_lb=value, reps=8))
        report = LabReport(drawn_on=date.today(), lab_name="Synthetic lab")
        report.results = [LabResult(analyte="ApoB", value=95, unit="mg/dL")]
        db.add(report)
        db.commit()
        eid = equipment.id
    with food.begin() as connection:
        connection.execute(text("INSERT INTO tracker_food_products(id,nutrients) VALUES(1,:n),(2,:n2)"),
                           {"n": '{"proteins":30,"energy":300}', "n2": '{"energy":200}'})
        connection.execute(text("INSERT INTO tracker_food_entries(id,product_id,eaten_on,servings) VALUES(1,1,:day,1),(2,2,:day,1)"),
                           {"day": date.today().isoformat()})
        connection.execute(text("INSERT INTO tracker_food_targets(nutrient,value) VALUES('proteins', 160)"))
    response = client.get("/progress", params={"machine": eid, "reps": 8, "days": 90})
    assert response.status_code == 200, response.text[:400]
    assert "Synthetic Nautilus 762" in response.text
    assert "Improving" in response.text
    assert "112" in response.text
    assert "ApoB" in response.text
    assert "160" in response.text
    assert "0 fully reported" not in response.text  # incomplete protein day never counts as complete
    assert "No days with protein values for every logged food item" in response.text
    with Session(engine) as db:
        assert len(list(db.scalars(select(VitalReading)))) == 2
        assert len(list(db.scalars(select(LabResult)))) == 1


def test_762_template_and_auth_boundaries_static():
    import ast
    from jinja2 import Environment
    for path in ("app/progress_models762.py", "app/progress_calc762.py",
                 "app/routers/progress762.py"):
        ast.parse((ROOT/path).read_text(), filename=path)
    Environment().parse((ROOT/"app/templates/progress762.html").read_text())
    router = (ROOT/"app/routers/progress762.py").read_text()
    assert "Depends(get_scoped_db390)" in router
    assert "Depends(get_food_read_engine406)" in router
    assert 'ProgressMarker762' in router
    main = (ROOT/"app/main.py").read_text()
    assert "app.include_router(progress762.router)" in main

def test_763_waist_change_requires_two_distinct_dates():
    from app.progress_calc762 import metric_change_details762
    from types import SimpleNamespace
    today = date.today()
    samples = [SimpleNamespace(measured_on=today, waist_navel=103),
               SimpleNamespace(measured_on=today, waist_navel=102)]
    assert metric_change_details762(samples, "waist_navel") is None
    samples.append(SimpleNamespace(measured_on=today-timedelta(days=7), waist_navel=100))
    details = metric_change_details762(samples, "waist_navel")
    assert details == {"delta": 2.0, "first": today-timedelta(days=7),
                       "last": today, "days": 2}


def test_763_bodyfat_summary_skips_newer_partial_records(progress_client762):
    client, _, _ = progress_client762
    today = date.today()
    first = client.post("/progress/composition/save", data={
        "measured_on": (today-timedelta(days=7)).isoformat(),
        "method": "BIA", "body_fat_pct": "24.7"
    }, follow_redirects=True)
    assert first.status_code == 200
    second = client.post("/progress/composition/save", data={
        "measured_on": today.isoformat(), "method": "DEXA",
        "mass_unit": "lb", "fat_free_mass_kg": "170"
    }, follow_redirects=True)
    assert second.status_code == 200
    page = client.get("/progress").text
    assert f"24.7% · BIA · {today-timedelta(days=7)}" in page
    assert "Need 2 dates" in page


def test_763_schema_production_review_on_pinned_candidate():
    # Execute the real, read-only migration guard against the isolated QA
    # worktree and its exact target; no live user database is opened.
    import subprocess
    import sys
    target = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    cmd = [sys.executable, str(ROOT/"scripts/tracker_schema_review763.py"),
           "--root", str(ROOT),
           "--base", "04fd141daa17fd2055f9177527296eb9165a59d2",
           "--target", target]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "RELEASE_763_PROGRESS_SCHEMA_REVIEW=PASSED" in result.stdout
    runner = (ROOT/"scripts/tracker-release.sh").read_text()
    remote = (ROOT/"scripts/tracker_prod_remote568.sh").read_text()
    assert "--reviewed-progress-762" in runner
    assert "RELEASE_763_PROGRESS_SCHEMA_REVIEW=PASSED" in runner
    assert "DEPLOY_EXTRA=(--reviewed-progress-762 --db-migration)" in remote
    invalid = subprocess.run(cmd[:5] + [target, "--target", target],
                             capture_output=True, text=True, check=False)
    assert invalid.returncode != 0
