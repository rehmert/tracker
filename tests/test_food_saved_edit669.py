"""Release 669: saved-product edits preserve references, validation and history."""
import json
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.food_read_engine406 import get_food_read_engine406
from app.routers import food


@pytest.fixture
def env():
    db_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    app = FastAPI()
    app.include_router(food.router)
    app.dependency_overrides[get_food_read_engine406] = lambda: db_engine
    with TestClient(app) as client:
        food.init_food_schema(db_engine)
        with db_engine.begin() as db:
            result = db.execute(text("""
                INSERT INTO tracker_food_products
                    (name,barcode,serving_description,nutrients,source)
                VALUES (:name,:barcode,:serving,:nutrients,'manual')
            """), {
                "name": "Original Greek Yogurt", "barcode": "123456789012",
                "serving": "1 container",
                "nutrients": json.dumps({
                    **{key: 0 for key in food.NUTRIENTS},
                    "energy": 100, "proteins": 20, "potassium": None,
                }),
            })
            product_id = result.lastrowid
            db.execute(text("""
                INSERT INTO tracker_food_entries(product_id,eaten_on,meal,servings)
                VALUES (:id,'2026-11-16','Breakfast',2)
            """), {"id": product_id})
            db.execute(text("""
                INSERT INTO tracker_food_favorites(product_id) VALUES (:id)
            """), {"id": product_id})
        yield client, db_engine, product_id
    db_engine.dispose()


def edit_form(client, product_id):
    page = client.get(f"/food/saved/{product_id}/edit?day=2026-11-16")
    assert page.status_code == 200
    token = re.search(r'name="version" value="([a-f0-9]{64})"', page.text)
    assert token is not None
    return {
        "day": "2026-11-16", "version": token.group(1),
        "name": "Updated Greek Yogurt", "serving_description": "170 g",
        "barcode": "123456789012", "confirm_history": "yes",
        **{key: "0" for key in food.NUTRIENTS},
        "energy": "120", "proteins": "21", "potassium": "",
    }


def test_669_edit_changes_saved_record_and_totals_without_new_entries(env):
    client, db_engine, product_id = env
    before = food.totals_for("2026-11-16", db_engine=db_engine)
    assert before["energy"] == 200
    page = client.get(f"/food/saved/{product_id}/edit?day=2026-11-16")
    assert "Original Greek Yogurt" in page.text
    assert "1 logged meal entry" in page.text

    result = client.post(
        f"/food/saved/{product_id}/edit", data=edit_form(client, product_id),
        follow_redirects=False,
    )
    assert result.status_code == 303
    assert f"/food/saved/{product_id}/edit?day=2026-11-16&saved=1" in result.headers["location"]
    with db_engine.connect() as db:
        row = db.execute(text(
            "SELECT id,name,serving_description,nutrients FROM tracker_food_products"
        )).mappings().one()
        entries = db.execute(text(
            "SELECT product_id,eaten_on,meal,servings FROM tracker_food_entries"
        )).one()
        favorite = db.execute(text(
            "SELECT product_id FROM tracker_food_favorites"
        )).scalar_one()
    assert row["id"] == product_id
    assert row["name"] == "Updated Greek Yogurt"
    assert row["serving_description"] == "170 g"
    assert json.loads(row["nutrients"])["potassium"] is None
    assert tuple(entries) == (product_id, "2026-11-16", "Breakfast", 2)
    assert favorite == product_id
    assert food.totals_for("2026-11-16", db_engine=db_engine)["energy"] == 240


def test_669_conflict_and_missing_confirmation_do_not_write(env):
    client, db_engine, product_id = env
    original = edit_form(client, product_id)
    missing_confirm = {**original, "confirm_history": ""}
    denied = client.post(f"/food/saved/{product_id}/edit",
                         data=missing_confirm, follow_redirects=False)
    assert denied.status_code == 422

    successful = client.post(
        f"/food/saved/{product_id}/edit", data=original, follow_redirects=False
    )
    assert successful.status_code == 303
    stale = client.post(
        f"/food/saved/{product_id}/edit",
        data={**original, "name": "Stale Overwrite"},
        follow_redirects=False,
    )
    assert stale.status_code == 409
    with db_engine.connect() as db:
        assert db.execute(text(
            "SELECT name FROM tracker_food_products WHERE id=:id"
        ), {"id": product_id}).scalar_one() == "Updated Greek Yogurt"


@pytest.mark.parametrize("changes", [
    {"name": ""}, {"name": "X" * 161},
    {"serving_description": ""}, {"serving_description": "S" * 81},
    {"barcode": "ABC"}, {"energy": "-1"}, {"energy": "nan"},
    {"energy": "100001"}, {"proteins": "inf"},
])
def test_669_invalid_fields_are_rejected_without_mutation(env, changes):
    client, db_engine, product_id = env
    form = {**edit_form(client, product_id), **changes}
    denied = client.post(f"/food/saved/{product_id}/edit",
                         data=form, follow_redirects=False)
    assert denied.status_code == 422
    with db_engine.connect() as db:
        assert db.execute(text(
            "SELECT name FROM tracker_food_products WHERE id=:id"
        ), {"id": product_id}).scalar_one() == "Original Greek Yogurt"


def test_669_rejects_missing_product_and_partial_nutrient_submission(env):
    client, db_engine, product_id = env
    assert client.get("/food/saved/999999/edit?day=2026-11-16").status_code == 404
    source = edit_form(client, product_id)
    del source["fat"]
    response = client.post(f"/food/saved/{product_id}/edit",
                           data=source, follow_redirects=False)
    assert response.status_code == 422
    assert client.post("/food/saved/999999/edit", data={
        **edit_form(client, product_id),
    }, follow_redirects=False).status_code == 404


def test_669_edit_links_in_saved_food_views():
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "app/templates/food.html"
    content = path.read_text(encoding="utf-8")
    assert content.count('/food/saved/{{ item.id }}/edit?day={{ day }}') == 3
    assert '/food/saved/{{ e.product_id }}/edit?day={{ day }}' in content
