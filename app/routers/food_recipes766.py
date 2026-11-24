"""Release 766 cooked recipe builder using the guarded Food storage engine.

Creates versioned saved foods (100 g cooked serving) without rewriting
historical journal entries. Ingredient formulas stay private to this engine.
"""
from __future__ import annotations

import json
import math

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from ..food_read_engine406 import get_food_read_engine406
from ..food_storage_guard391 import require_food_storage391
from ..templating import render
from .food import NUTRIENTS, init_food_schema

router = APIRouter(dependencies=[Depends(require_food_storage391)])


def init_recipes766(engine):
    init_food_schema(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS tracker_food_recipes766 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                cooked_g REAL NOT NULL,
                ingredients_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(product_id) REFERENCES tracker_food_products(id)
            )
        """)


def recipe_inputs766(name, cooked_raw, ids, servings):
    name = str(name or "").strip()
    if not 1 <= len(name) <= 100:
        raise HTTPException(422, "Recipe name must be 1–100 characters")
    try:
        cooked_g = float(cooked_raw)
    except (ValueError, TypeError, OverflowError):
        raise HTTPException(422, "Enter a valid cooked batch weight in grams") from None
    if not math.isfinite(cooked_g) or not 25 <= cooked_g <= 100000:
        raise HTTPException(422, "Cooked weight must be 25–100,000 grams")
    if len(ids) != len(servings) or len(ids) > 16:
        raise HTTPException(422, "Select up to 16 recipe ingredient rows")
    items = []
    for raw_id, raw_servings in zip(ids, servings):
        if str(raw_id or "").strip() == "":
            if str(raw_servings or "").strip() not in ("", "0"):
                raise HTTPException(422, "Choose a food for each entered quantity")
            continue
        try:
            product_id = int(raw_id)
            servings_value = float(raw_servings)
        except (ValueError, TypeError, OverflowError):
            raise HTTPException(422, "Invalid saved food or serving quantity") from None
        if product_id <= 0 or not math.isfinite(servings_value) or not 0 < servings_value <= 1000:
            raise HTTPException(422, "Each ingredient needs 0–1,000 positive servings")
        items.append({"product_id": product_id, "servings": servings_value})
    if not items:
        raise HTTPException(422, "Select at least one saved ingredient")
    return name, cooked_g, items


def recipe_nutrients766(conn, items, cooked_g):
    ids = {item["product_id"] for item in items}
    products = {}
    for product_id in ids:
        row = conn.execute(text("""
            SELECT id, nutrients FROM tracker_food_products WHERE id=:id
        """), {"id": product_id}).mappings().first()
        if row is None:
            raise HTTPException(422, f"Saved ingredient #{product_id} no longer exists")
        try:
            nutrients = json.loads(row["nutrients"])
        except (ValueError, TypeError):
            raise HTTPException(422, "An ingredient has invalid saved nutrients") from None
        if not isinstance(nutrients, dict):
            raise HTTPException(422, "An ingredient has invalid saved nutrients")
        products[product_id] = nutrients
    result = {}
    for key in NUTRIENTS:
        total = 0.0
        known = True
        for item in items:
            raw = products[item["product_id"]].get(key)
            if raw is None:
                known = False
                break
            try:
                number = float(raw)
            except (ValueError, TypeError, OverflowError):
                raise HTTPException(422, "Invalid ingredient nutrient value") from None
            if not math.isfinite(number) or number < 0 or number > 100000:
                raise HTTPException(422, "Ingredient nutrient value out of range")
            total += number * item["servings"]
        result[key] = round(total * 100 / cooked_g, 5) if known else None
    return result


def save_recipe766(conn, *, name, cooked_g, items, recipe_id=None):
    nutrients = recipe_nutrients766(conn, items, cooked_g)
    existing = None
    if recipe_id is not None:
        existing = conn.execute(text("""
            SELECT id FROM tracker_food_recipes766 WHERE id=:id
        """), {"id": recipe_id}).first()
        if existing is None:
            raise HTTPException(404, "Recipe not found")
    product = conn.execute(text("""
        INSERT INTO tracker_food_products
            (barcode, name, serving_description, nutrients, source)
        VALUES (NULL, :name, '100 g cooked', :nutrients, 'recipe-766')
    """), {"name": name, "nutrients": json.dumps(nutrients, sort_keys=True)})
    product_id = product.lastrowid
    values = {
        "name": name, "cooked": cooked_g, "items": json.dumps(items),
        "product": product_id,
    }
    if recipe_id is None:
        conn.execute(text("""
            INSERT INTO tracker_food_recipes766
                (name, product_id, cooked_g, ingredients_json)
            VALUES (:name,:product,:cooked,:items)
        """), values)
    else:
        conn.execute(text("""
            UPDATE tracker_food_recipes766
            SET name=:name, product_id=:product, cooked_g=:cooked,
                ingredients_json=:items
            WHERE id=:id
        """), {**values, "id": recipe_id})
    return product_id


@router.get("/food/recipes")
def recipes_page766(
    request: Request, edit: int = 0,
    db_engine=Depends(get_food_read_engine406),
):
    init_recipes766(db_engine)
    with db_engine.connect() as conn:
        products = [dict(row) for row in conn.execute(text("""
            SELECT id,name,serving_description FROM tracker_food_products
            ORDER BY name COLLATE NOCASE,id DESC LIMIT 250
        """)).mappings()]
        records = [dict(row) for row in conn.execute(text("""
            SELECT id,name,product_id,cooked_g,ingredients_json,created_at
            FROM tracker_food_recipes766 ORDER BY id DESC LIMIT 100
        """)).mappings()]
    for row in records:
        row["ingredients"] = json.loads(row["ingredients_json"])
    editing = next((row for row in records if row["id"] == edit), None)
    choices = editing["ingredients"][:] if editing else []
    while len(choices) < 6:
        choices.append({"product_id": "", "servings": ""})
    return render(
        request, "food_recipes766.html", products=products, recipes=records,
        editing=editing, choices=choices[:16],
    )


@router.post("/food/recipes")
@router.post("/food/recipes/{recipe_id}")
async def recipe_save766(
    request: Request, recipe_id: int | None = None,
    db_engine=Depends(get_food_read_engine406),
):
    form = await request.form()
    name, cooked_g, items = recipe_inputs766(
        form.get("name"), form.get("cooked_g"),
        form.getlist("product_id"), form.getlist("servings"),
    )
    init_recipes766(db_engine)
    with db_engine.begin() as conn:
        save_recipe766(
            conn, name=name, cooked_g=cooked_g, items=items,
            recipe_id=recipe_id,
        )
    return RedirectResponse("/food/recipes?saved=1#saved-recipes766", status_code=303)


@router.post("/food/recipes/{recipe_id}/delete")
def recipe_delete766(
    recipe_id: int, db_engine=Depends(get_food_read_engine406),
):
    init_recipes766(db_engine)
    with db_engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM tracker_food_recipes766 WHERE id=:id"),
            {"id": recipe_id},
        )
        if result.rowcount != 1:
            raise HTTPException(404, "Recipe not found")
    # Historical Food Journal and saved-food product records are untouched.
    return RedirectResponse("/food/recipes?deleted=1#saved-recipes766", status_code=303)
