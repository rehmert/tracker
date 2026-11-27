"""Release 766 integrated UX, recipe, device import and weekly trends.

Synthetic isolated SQLite, no real Tracker records, network or user files.
"""
from datetime import date, datetime, timedelta
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jinja2 import Environment
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.main import app
from app.models import Compound, DoseLog, Vial, VitalReading
from app.device_models766 import DeviceDay766
from app.progress_models762 import ProgressMeasure762
from app.workout_models654 import WorkoutSession654
from app.routers.food_recipes766 import (
    init_recipes766, recipe_inputs766, recipe_nutrients766, save_recipe766,
)
from app.routers.device_import766 import parse_csv766, normalize766, store766
from app.routers.report_trends766 import weekly_rows766

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def engine():
    database = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(database)
    yield database
    database.dispose()


def test_766_recipe_calculates_per_100g_without_changing_old_food(engine):
    init_recipes766(engine)
    with engine.begin() as db:
        p1 = db.execute(text("""
            INSERT INTO tracker_food_products
              (name, serving_description, nutrients, source)
            VALUES ('Synthetic A', '100 g', :nutrients,'manual')
        """), {"nutrients": json.dumps({
            "energy":100, "proteins":20, "carbohydrates":6, "fat":3,
        })}).lastrowid
        p2 = db.execute(text("""
            INSERT INTO tracker_food_products
              (name, serving_description, nutrients, source)
            VALUES ('Synthetic B', '1 serving', :nutrients,'manual')
        """), {"nutrients": json.dumps({
            "energy":200, "proteins":10, "carbohydrates":30, "fat":4,
        })}).lastrowid
        name, cooked, items = recipe_inputs766(
            "Synthetic cooked batch", "250",
            [str(p1), str(p2)], ["2", "1"],
        )
        computed = recipe_nutrients766(db, items, cooked)
        assert computed["energy"] == 160
        assert computed["proteins"] == 20
        assert computed["carbohydrates"] == 16.8
        assert computed["sodium"] is None  # unreported stays unknown
        old_product = save_recipe766(
            db, name=name, cooked_g=cooked, items=items,
        )
        recipe_id = db.execute(text(
            "SELECT id FROM tracker_food_recipes766"
        )).scalar_one()
        new_product = save_recipe766(
            db, name="Synthetic version 2", cooked_g=500, items=items,
            recipe_id=recipe_id,
        )
        assert new_product != old_product
        source = db.execute(text("""
            SELECT name, nutrients FROM tracker_food_products WHERE id=:id
        """), {"id":old_product}).one()
        assert source[0] == name
        assert json.loads(source[1])["energy"] == 160
        current_id = db.execute(text(
            "SELECT product_id FROM tracker_food_recipes766 WHERE id=:id"
        ), {"id":recipe_id}).scalar_one()
        assert current_id == new_product
        db.execute(text(
            "DELETE FROM tracker_food_recipes766 WHERE id=:id"
        ), {"id":recipe_id})
        assert db.execute(text(
            "SELECT id FROM tracker_food_products WHERE id=:id"
        ), {"id":old_product}).first() is not None


@pytest.mark.parametrize("name,weight,ids,amounts", [
    ("", "400", ["1"], ["1"]),
    ("Batch", "0", ["1"], ["1"]),
    ("Batch", "inf", ["1"], ["1"]),
    ("Batch", "300", [], []),
    ("Batch", "300", ["3"], ["-1"]),
    ("Batch", "300", ["0"], ["2"]),
    ("Batch", "300", ["1"], ["nan"]),
    ("Batch", "300", ["", "1"], ["2", "1"]),
])
def test_766_recipe_rejects_bad_inputs(name,weight,ids,amounts):
    with pytest.raises(HTTPException) as error:
        recipe_inputs766(name, weight, ids, amounts)
    assert error.value.status_code == 422


def test_766_device_csv_enforces_bounds_and_atomic_duplicates():
    today = date.today().isoformat()
    content = (
        "date,steps,sleep_hours,resting_bpm,glucose_avg_mgdl\n"
        f"{today},8034,6.5,70,104\n"
    ).encode()
    rows = parse_csv766(content)
    assert rows[0]["steps"] == 8034
    assert rows[0]["sleep_hours"] == 6.5
    with pytest.raises(HTTPException):
        parse_csv766(content + f"{today},9000,7,65,98\n".encode())
    with pytest.raises(HTTPException):
        parse_csv766(b"date,bad_field\n2026-01-02,10\n")
    with pytest.raises(HTTPException):
        parse_csv766(b"date,steps\n2026-01-02,=SUM(1+2)\n")
    with pytest.raises(HTTPException):
        parse_csv766(b"a" * 262145)
    with pytest.raises(HTTPException):
        normalize766({"date":today,"sleep_hours":"25"})


def test_766_device_upsert_is_scoped_and_idempotent(engine):
    today = date.today()
    with Session(engine) as db:
        record = normalize766({"date":today.isoformat(), "steps":"8000"})
        assert store766(db, "Wearable A", [record]) == dict(added=1, updated=0, skipped=0)
        assert store766(db, "Wearable A", [record]) == dict(added=0, updated=0, skipped=1)
        new_record = normalize766({"date":today.isoformat(), "steps":"9000"})
        assert store766(db, "Wearable A", [new_record], replace=True) == dict(added=0, updated=1, skipped=0)
        assert store766(db, "Wearable B", [record]) == dict(added=1, updated=0, skipped=0)
        entries = db.scalars(select(DeviceDay766)).all()
        assert len(entries) == 2
        assert {row.source:row.steps for row in entries} == {
            "Wearable A":9000, "Wearable B":8000,
        }


def test_766_weekly_uses_observed_days_and_overlapping_device_sources(engine):
    observed = date(2026, 11, 23)  # Monday for deterministic week coverage
    previous = observed - timedelta(days=1)
    with Session(engine) as db:
        db.add_all([
            VitalReading(measured_at=datetime(2026,11,23,7), weight_kg=100),
            VitalReading(measured_at=datetime(2026,11,23,21), weight_kg=99),
            VitalReading(measured_at=datetime(2026,11,22,7), weight_kg=101),
            ProgressMeasure762(measured_on=observed, waist_navel=110),
            WorkoutSession654(
                started_at=datetime(2026,11,23,10),
                completed_at=datetime(2026,11,23,11),
            ),
            DeviceDay766(
                measured_on=observed, source="Synthetic A", steps=8000,
                sleep_hours=6.5,
            ),
            DeviceDay766(
                measured_on=observed, source="Synthetic B", steps=8100,
                sleep_hours=None,
            ),
        ])
        compound = Compound(name="Synthetic 766 trend",category="peptide")
        db.add(compound)
        db.flush()
        vial = Vial(compound_id=compound.id, content_value=10,
                    content_unit="mg", status="in_use")
        db.add(vial)
        db.flush()
        db.add(DoseLog(
            vial_id=vial.id, taken_at=datetime(2026,11,23,8),
            entered_value=1, entered_unit="mg", amount_base=1000, kind="dose",
        ))
        db.commit()
        rows, units = weekly_rows766(db, 28, observed)
        assert rows[0]["week"] == observed
        assert rows[0]["weight_days"] == 1
        assert rows[0]["waist_days"] == 1
        assert rows[0]["workouts"] == 1
        assert rows[0]["doses"] == 1
        assert rows[0]["step_days"] == 1
        assert rows[0]["steps"] == 8100
        assert rows[0]["sleep_days"] == 1
        assert rows[0]["sleep"] == 6.5
        assert rows[0]["protein"] is None
        assert rows[1]["weight_days"] == 1
        assert units["food_available"] is False


def test_766_recipe_and_trend_optional_food_coverage(engine):
    init_recipes766(engine)
    today = date(2026,11,23)
    with engine.begin() as conn:
        pid = conn.execute(text("""
            INSERT INTO tracker_food_products
              (name, serving_description, nutrients, source)
            VALUES ('Synthetic Protein', '1 portion', :nutrients, 'manual')
        """), {"nutrients":json.dumps({"proteins":22})}).lastrowid
        conn.execute(text("""
            INSERT INTO tracker_food_entries (product_id,eaten_on,meal,servings)
            VALUES (:id,:date,'Lunch',1)
        """), {"id":pid,"date":today.isoformat()})
    with Session(engine) as db:
        rows, meta = weekly_rows766(db, 28, today, food_engine=engine)
        assert meta["food_available"] is True
        assert rows[0]["protein"] == 22.0
        assert rows[0]["protein_days"] == 1
    with engine.begin() as conn:
        pid = conn.execute(text("""
            INSERT INTO tracker_food_products
              (name, serving_description, nutrients, source)
            VALUES ('Synthetic Unknown Protein', '1 portion', :nutrients, 'manual')
        """), {"nutrients":json.dumps({"proteins":None})}).lastrowid
        conn.execute(text("""
            INSERT INTO tracker_food_entries (product_id,eaten_on,meal,servings)
            VALUES (:id,:date,'Lunch',1)
        """), {"id":pid,"date":today.isoformat()})
    with Session(engine) as db:
        rows, _ = weekly_rows766(db, 28, today, food_engine=engine)
        assert rows[0]["protein"] is None
        assert rows[0]["protein_days"] == 0


def test_766_routes_and_templates_render_with_existing_auth():
    with TestClient(app, follow_redirects=False) as client:
        for url, fragment in (
            ("/device-import", "Device Data"),
            ("/reports/trends", "Weekly Integrated Trends"),
            ("/reports/trends.csv", "week_start,week_end"),
            ("/food/recipes", "Cooked Recipe Builder"),
        ):
            response = client.get(url)
            assert response.status_code == 200, (url, response.text[:400])
            assert fragment in response.text
        assert "attachment" in client.get("/reports/trends.csv").headers["content-disposition"]


def test_766_exact_mobile_contracts_and_existing_action_paths():
    for path in (
        "app/templates/vials.html", "app/templates/workout_quick659.html",
        "app/templates/food_recipes766.html", "app/templates/device_import766.html",
        "app/templates/report_trends766.html", "app/templates/quick_entry.html",
        "app/templates/progress762.html", "app/templates/mobile_today509.html",
    ):
        Environment().parse((ROOT/path).read_text())
    vials = (ROOT/"app/templates/vials.html").read_text()
    gym = (ROOT/"app/templates/workout_quick659.html").read_text()
    main = (ROOT/"app/main.py").read_text()
    assert vials.count('id="tracker-vials-sortable"') == 1
    assert 'id="vial766-mobile-cards"' in vials
    assert 'id="vial766-full-toggle"' in vials
    assert 'id="vial766-full-table"' in vials
    assert "[:50]" in vials
    assert "bulk-vial-check" in vials
    assert gym.count('class="workout766-handoff"') == 1
    assert gym.index('class="workout766-handoff"') < gym.index('id="workout659-log-form"')
    assert 'id="workout659-save"' in gym
    assert 'workout668-draft-save' in gym
    assert "tracker-gym-handoff766.js?v=794.1" in gym
    assert "tracker-vial-mobile-cards766.js?v=766" in vials
    assert main.index("app.include_router(report_trends766.router)") < main.index("app.include_router(consolidated_reports.router)")
    for name in ("tracker-vial-mobile-cards766","tracker-gym-handoff766",
                 "tracker-recipes766","tracker-device-import766","tracker-trends766"):
        assert (ROOT/f"app/static/css/{name}.css").exists()
