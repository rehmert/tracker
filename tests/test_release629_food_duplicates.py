"""Release 629: isolated saved-food duplicate review and consolidation tests."""
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import Environment
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

from app.routers import food, food_bundle376, food_duplicates629 as duplicates

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def food_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    food_bundle376.init_schema(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def add_food(engine, name="Greek Yogurt", serving="170 g",
             nutrients=None, barcode="123", favorite=False,
             logged=False, template=False):
    values = nutrients if nutrients is not None else {
        "energy": 100.0, "proteins": 17.0, "carbohydrates": 6.0,
        "fat": 0.0, "vitamin-b12": 1.2, "potassium": None,
    }
    with engine.begin() as db:
        pk = db.execute(text("""
            INSERT INTO tracker_food_products
                (name,serving_description,nutrients,barcode,source)
            VALUES (:name,:serving,:nutrients,:barcode,'manual')
        """), {
            "name": name, "serving": serving,
            "nutrients": json.dumps(values), "barcode": barcode,
        }).lastrowid
        if logged:
            db.execute(text("""
                INSERT INTO tracker_food_entries
                    (product_id,eaten_on,meal,servings)
                VALUES (:id,'2026-11-14','Breakfast',2)
            """), {"id": pk})
        if favorite:
            db.execute(text("""
                INSERT INTO tracker_food_favorites(product_id)
                VALUES (:id)
            """), {"id": pk})
        if template:
            tid = db.execute(text("""
                INSERT INTO tracker_food_meal_templates(name)
                VALUES ('Morning')
            """)).lastrowid
            db.execute(text("""
                INSERT INTO tracker_food_meal_template_items
                    (template_id,product_id,servings,meal)
                VALUES (:tid,:id,1,'Breakfast')
            """), {"tid": tid, "id": pk})
    return pk


def test_629_name_groups_show_every_macro_micro_value(food_engine):
    first = add_food(food_engine, logged=True)
    second = add_food(food_engine, name=" greek   yogurt ",
                      nutrients={"energy": 110.0, "proteins": 18.0,
                                 "carbohydrates": 6.0, "fat": 0,
                                 "vitamin-b12": None})
    report = duplicates.duplicate_groups629(food_engine)
    assert report["truncated"] is False
    assert len(report["groups"]) == 1
    group = report["groups"][0]
    assert {item["id"] for item in group["versions"]} == {first, second}
    assert group["different_values"]
    assert group["equivalent_sets"] == []
    by_id = {item["id"]: item for item in group["versions"]}
    assert len(by_id[first]["measurements"]) == len(food.NUTRIENTS)
    assert by_id[first]["measurements"]["vitamin-b12"] == 1.2
    assert by_id[first]["measurements"]["potassium"] is None
    assert by_id[second]["measurements"]["energy"] == 110.0
    assert "energy" in group["different_nutrients"]
    assert "vitamin-b12" in group["different_nutrients"]


def test_629_equivalent_merge_preserves_logged_totals_templates_favorites(food_engine):
    keeper = add_food(food_engine, logged=True, template=True)
    redundant = add_food(food_engine, name="GREEK yogurt",
                         logged=True, favorite=True, template=True)
    report = duplicates.duplicate_groups629(food_engine)
    assert len(report["groups"][0]["equivalent_sets"][0]) == 2
    before = food.totals_for("2026-11-14", db_engine=food_engine)
    assert duplicates.merge_equivalent629(food_engine, keeper, [redundant]) == 1
    after = food.totals_for("2026-11-14", db_engine=food_engine)
    assert after == before
    with food_engine.connect() as db:
        assert db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_products
        """)).scalar_one() == 1
        assert db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_entries
            WHERE product_id=:id
        """), {"id": keeper}).scalar_one() == 2
        assert db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_meal_template_items
            WHERE product_id=:id
        """), {"id": keeper}).scalar_one() == 2
        assert db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_favorites
            WHERE product_id=:id
        """), {"id": keeper}).scalar_one() == 1


@pytest.mark.parametrize("variation", [
    {"nutrients": {"energy": 101.0}},
    {"nutrients": {"energy": None}},
    {"serving": "100 g"},
    {"barcode": "DIFFERENT"},
    {"name": "Plain yogurt"},
])
def test_629_non_equivalent_merge_is_atomic_and_rejected(food_engine, variation):
    keeper = add_food(food_engine, logged=True, favorite=True)
    different = add_food(food_engine, logged=True, template=True, **variation)
    with pytest.raises(ValueError):
        duplicates.merge_equivalent629(food_engine, keeper, [different])
    with food_engine.connect() as db:
        assert db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_products"
        )).scalar_one() == 2
        assert db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_entries"
        )).scalar_one() == 2
        assert db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_meal_template_items"
        )).scalar_one() == 1


@pytest.mark.parametrize("keep,others", [
    (1, []), (1, [1]), (1, [2, 2]), (0, [2]),
    (1, ["2"]), (True, [2]),
])
def test_629_invalid_selection_rejected_before_database_access(keep, others):
    with pytest.raises(ValueError):
        duplicates.merge_equivalent629(None, keep, others)


def test_629_review_template_and_route_wiring():
    template = (ROOT / "app/templates/food_duplicates629.html").read_text()
    Environment().parse(template)
    assert "Macro" in template
    assert "Micronutrients" in template
    assert 'name="keep_id"' in template
    assert 'name="remove_id"' in template
    assert "item.measurements[key]" in template
    assert "group.equivalent_sets" in template
    assert 'action="/food/duplicates/merge"' in template
    assert "/food/duplicates" in (
        ROOT / "app/templates/food.html"
    ).read_text()
    main = (ROOT / "app/main.py").read_text()
    assert "app.include_router(food_duplicates629.router)" in main
    assert '"/food/duplicates"' in (
        ROOT / "app/routers/food_duplicates629.py"
    ).read_text()


def test_629_authenticated_review_and_explicit_merge_routes(food_engine):
    from app.food_read_engine406 import get_food_read_engine406
    from app.food_storage_guard391 import require_food_storage391

    keeper = add_food(food_engine, logged=True)
    redundant = add_food(food_engine, name="GREEK YOGURT",
                         logged=True, favorite=True)
    app = FastAPI()
    app.include_router(duplicates.router)
    app.dependency_overrides[get_food_read_engine406] = lambda: food_engine
    app.dependency_overrides[require_food_storage391] = lambda: None
    with TestClient(app) as browser:
        review = browser.get("/food/duplicates")
        assert review.status_code == 200
        assert "Greek Yogurt" in review.text
        assert "Vitamin B12" in review.text
        assert "1.2" in review.text
        assert f'#{keeper}' in review.text
        assert f'#{redundant}' in review.text
        merge = browser.post("/food/duplicates/merge", data={
            "keep_id": str(keeper),
            "remove_id": str(redundant),
            "csrf_token": "synthetic-form-token",
        }, follow_redirects=False)
        assert merge.status_code == 303
        assert merge.headers["location"] == "/food/duplicates?merged=1"
        assert "consolidated" in browser.get(merge.headers["location"]).text

        refused = browser.post("/food/duplicates/merge", data={
            "keep_id": str(keeper),
            "remove_id": str(keeper),
        }, follow_redirects=False)
        assert refused.status_code == 422


def test_629_same_barcode_with_different_names_is_reviewed_not_merged(food_engine):
    one = add_food(food_engine, name="Brand A Organic Yogurt", barcode="00099")
    two = add_food(food_engine, name="Organic Yogurt Brand A", barcode="00099")
    report = duplicates.duplicate_groups629(food_engine)
    assert len(report["groups"]) == 1
    versions = {item["id"] for item in report["groups"][0]["versions"]}
    assert versions == {one, two}
    assert report["groups"][0]["equivalent_sets"] == []
    with pytest.raises(ValueError):
        duplicates.merge_equivalent629(food_engine, one, [two])
