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


def test_630_remove_mismatched_unused_preserves_history_and_moves_templates(food_engine):
    keeper = add_food(food_engine, logged=True)
    old = add_food(food_engine, nutrients={"energy": 125.0},
                   template=True, favorite=True)
    before = food.totals_for("2026-11-14", db_engine=food_engine)
    assert duplicates.remove_unused_mismatch630(food_engine, keeper, old) == 1
    assert food.totals_for("2026-11-14", db_engine=food_engine) == before
    with food_engine.connect() as db:
        assert db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_products WHERE id=:id"
        ), {"id": old}).scalar_one() == 0
        assert db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_meal_template_items WHERE product_id=:id"
        ), {"id": keeper}).scalar_one() == 1
        assert db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_favorites WHERE product_id=:id"
        ), {"id": keeper}).scalar_one() == 1


def test_630_reject_mismatched_removal_when_historical_meals_exist(food_engine):
    keeper = add_food(food_engine)
    old = add_food(food_engine, nutrients={"energy": 125.0}, logged=True)
    before = food.totals_for("2026-11-14", db_engine=food_engine)
    with pytest.raises(ValueError, match="historical"):
        duplicates.remove_unused_mismatch630(food_engine, keeper, old)
    assert food.totals_for("2026-11-14", db_engine=food_engine) == before


def test_630_mark_distinct_hides_group_until_values_change(food_engine):
    one = add_food(food_engine, logged=True)
    two = add_food(food_engine, nutrients={"energy": 125.0}, logged=True)
    report = duplicates.duplicate_groups629(food_engine)
    fingerprint = report["groups"][0]["fingerprint"]
    duplicates.mark_distinct630(food_engine, fingerprint)
    assert duplicates.duplicate_groups629(food_engine)["groups"] == []
    assert duplicates.duplicate_groups629(food_engine, show_reviewed=True)["groups"][0]["reviewed"]
    with food_engine.begin() as db:
        db.execute(text(
            "UPDATE tracker_food_products SET serving_description='180 g' WHERE id=:id"
        ), {"id": two})
    assert len(duplicates.duplicate_groups629(food_engine)["groups"]) == 1
    assert food.totals_for("2026-11-14", db_engine=food_engine)["energy"] == 450.0


def test_630_new_resolution_routes_are_available(food_engine):
    from app.food_read_engine406 import get_food_read_engine406
    from app.food_storage_guard391 import require_food_storage391
    keep = add_food(food_engine, logged=True)
    unused = add_food(food_engine, nutrients={"energy": 125.0})
    app = FastAPI()
    app.include_router(duplicates.router)
    app.dependency_overrides[get_food_read_engine406] = lambda: food_engine
    app.dependency_overrides[require_food_storage391] = lambda: None
    with TestClient(app) as browser:
        response = browser.post("/food/duplicates/resolve-unused", data={
            "keep_id": str(keep), "remove_id": str(unused),
        }, follow_redirects=False)
        assert response.status_code == 303
        assert "resolved=1" in response.headers["location"]


def test_630_review_template_exposes_mismatched_resolution_controls():
    template = (ROOT / "app/templates/food_duplicates629.html").read_text()
    Environment().parse(template)
    assert 'action="/food/duplicates/resolve-unused"' in template
    assert 'action="/food/duplicates/keep-distinct"' in template
    assert "item.log_count == 0" in template
    assert "group.reviewed" in template
    assert "group.fingerprint" in template


def test_630_unauthorized_removal_does_not_change_food_records(food_engine):
    keep = add_food(food_engine, name="Greek Yogurt", barcode="abc")
    other = add_food(food_engine, name="Different Food", barcode="xyz")
    with pytest.raises(ValueError, match="not direct duplicate"):
        duplicates.remove_unused_mismatch630(food_engine, keep, other)
    with food_engine.connect() as db:
        assert db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_products"
        )).scalar_one() == 2


def test_630_invalid_review_fingerprint_rejected(food_engine):
    with pytest.raises(ValueError, match="Invalid review selection"):
        duplicates.mark_distinct630(food_engine, "not-a-valid-fingerprint")


def test_641_reassign_logged_meals_preserves_meal_identity_and_updates_totals(food_engine):
    old = add_food(food_engine, logged=True, favorite=True, template=True,
                   nutrients={"energy": 120.0, "proteins": 8.0})
    keeper = add_food(food_engine, nutrients={"energy": 200.0, "proteins": 20.0})
    with food_engine.connect() as db:
        before = db.execute(text("""
            SELECT id, eaten_on, meal, servings FROM tracker_food_entries
            WHERE product_id=:id
        """), {"id": old}).one()
    assert food.totals_for("2026-11-14", db_engine=food_engine)["energy"] == 240
    assert duplicates.reassign_logged_uses641(food_engine, keeper, old, 1) == 1
    assert food.totals_for("2026-11-14", db_engine=food_engine)["energy"] == 400
    with food_engine.connect() as db:
        after = db.execute(text("""
            SELECT id, eaten_on, meal, servings FROM tracker_food_entries
            WHERE product_id=:id
        """), {"id": keeper}).one()
        assert after == before
        # Reassign affects only the logs, not favorites/templates.
        assert db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_meal_template_items
            WHERE product_id=:id
        """), {"id": old}).scalar_one() == 1
    # The previously used product becomes removable, and its remaining
    # favorite/template references are reconciled in the existing operation.
    assert duplicates.remove_unused_mismatch630(food_engine, keeper, old) == 1
    with food_engine.connect() as db:
        assert db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_products WHERE id=:id
        """), {"id": old}).scalar_one() == 0
        assert db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_meal_template_items
            WHERE product_id=:id
        """), {"id": keeper}).scalar_one() == 1


def test_641_reassignment_rejects_stale_count_and_unrelated_food(food_engine):
    old = add_food(food_engine, logged=True)
    keeper = add_food(food_engine, nutrients={"energy": 150})
    unrelated = add_food(food_engine, name="Some other food", barcode="777")
    with pytest.raises(ValueError, match="Logged uses changed"):
        duplicates.reassign_logged_uses641(food_engine, keeper, old, 2)
    with pytest.raises(ValueError, match="not direct duplicate"):
        duplicates.reassign_logged_uses641(food_engine, unrelated, old, 1)
    with food_engine.connect() as db:
        assert db.execute(text("""
            SELECT product_id FROM tracker_food_entries
        """)).scalar_one() == old


def test_641_existing_resolution_route_reassigns_then_removes(food_engine):
    from app.food_read_engine406 import get_food_read_engine406
    from app.food_storage_guard391 import require_food_storage391
    old = add_food(food_engine, logged=True)
    keeper = add_food(food_engine, nutrients={"energy": 190})
    app = FastAPI()
    app.include_router(duplicates.router)
    app.dependency_overrides[get_food_read_engine406] = lambda: food_engine
    app.dependency_overrides[require_food_storage391] = lambda: None
    with TestClient(app) as browser:
        bad = browser.post("/food/duplicates/resolve-unused", data={
            "keep_id": str(keeper), "remove_id": str(old),
            "expected_count": "2",
        }, follow_redirects=False)
        assert bad.status_code == 422
        good = browser.post("/food/duplicates/resolve-unused", data={
            "keep_id": str(keeper), "remove_id": str(old),
            "expected_count": "1",
        }, follow_redirects=False)
        assert good.status_code == 303
        assert good.headers["location"] == "/food/duplicates?reassigned=1"
        assert "1 logged meal entry reassigned" in browser.get(
            good.headers["location"]
        ).text
        delete = browser.post("/food/duplicates/resolve-unused", data={
            "keep_id": str(keeper), "remove_id": str(old),
        }, follow_redirects=False)
        assert delete.status_code == 303
        assert delete.headers["location"] == "/food/duplicates?resolved=1"


def test_641_unused_removal_checkbox_handler_is_not_applied():
    source = (ROOT / "app/static/js/tracker-food-duplicates629.js").read_text()
    assert 'form.food629-merge:not(.food630-resolve)' in source
    assert "form.food630-resolve, form.food641-reassign" in source
    template = (ROOT / "app/templates/food_duplicates629.html").read_text()
    assert 'name="expected_count"' in template
    assert 'action="/food/duplicates/resolve-unused"' in template
