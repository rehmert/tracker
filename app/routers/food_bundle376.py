"""Release 376: food search, meal templates and weekly nutrition."""
import json
from datetime import date, timedelta

from fastapi import Depends, APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from . import food
from .food_quick375 import selected_day, food_redirect, MEALS

from ..food_storage_guard391 import require_food_storage391

router = APIRouter(
    dependencies=[Depends(require_food_storage391)]
)


def init_schema(db_engine=None):
    selected_engine = (
        food.engine if db_engine is None else db_engine
    )
    food.init_food_schema(selected_engine)
    with selected_engine.begin() as db:
        db.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS tracker_food_meal_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS tracker_food_meal_template_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                servings REAL NOT NULL,
                meal TEXT NOT NULL,
                FOREIGN KEY(template_id)
                    REFERENCES tracker_food_meal_templates(id),
                FOREIGN KEY(product_id)
                    REFERENCES tracker_food_products(id)
            )
        """)


def search_products(query, db_engine=None):
    """Read-only saved-product search; latest matching records first."""
    value = str(query or "").strip()[:100]
    if not value:
        return []

    selected_engine = (
        food.engine if db_engine is None else db_engine
    )
    init_schema(selected_engine)
    with selected_engine.connect() as db:
        rows = db.execute(text("""
            SELECT p.id, p.name, p.barcode,
                   p.serving_description, p.nutrients,
                   COALESCE(
                       (SELECT e.meal FROM tracker_food_entries e
                        WHERE e.product_id=p.id
                        ORDER BY e.id DESC LIMIT 1),
                       'Snack'
                   ) AS meal,
                   COALESCE(
                       (SELECT e.servings FROM tracker_food_entries e
                        WHERE e.product_id=p.id
                        ORDER BY e.id DESC LIMIT 1),
                       1
                   ) AS servings
            FROM tracker_food_products p
            WHERE instr(lower(p.name), lower(:query)) > 0
               OR instr(COALESCE(p.barcode,''), :query) > 0
            ORDER BY p.id DESC
            LIMIT 30
        """), {"query": value}).mappings().all()

    return [dict(item) for item in rows]


def weekly_summary(day, db_engine=None):
    """Seven days of logged totals, ending on selected day."""
    end = date.fromisoformat(day)
    start = end - timedelta(days=6)

    selected_engine = (
        food.engine if db_engine is None else db_engine
    )
    with selected_engine.connect() as db:
        rows = db.execute(text("""
            SELECT e.eaten_on, e.servings, p.nutrients
            FROM tracker_food_entries e
            JOIN tracker_food_products p
                ON p.id=e.product_id
            WHERE e.eaten_on BETWEEN :start AND :end
        """), {
            "start": start.isoformat(),
            "end": end.isoformat(),
        }).all()

    keys = ("energy", "proteins", "carbohydrates", "fat")
    days = {}

    for offset in range(7):
        current = start + timedelta(days=offset)
        stamp = current.isoformat()
        days[stamp] = {
            "date": stamp,
            "label": current.strftime("%a"),
            "foods": 0,
            "reported": {key: 0 for key in keys},
            "totals": {key: 0.0 for key in keys},
        }

    for eaten_on, servings, nutrient_json in rows:
        item = days[eaten_on]
        values = json.loads(nutrient_json)
        item["foods"] += 1

        for key in keys:
            raw = values.get(key)
            if raw is not None:
                item["reported"][key] += 1
                item["totals"][key] += food.to_float(raw) * servings

    result = list(days.values())
    maximum = max(
        (day["totals"]["energy"] for day in result),
        default=0,
    )

    for item in result:
        item["calorie_width"] = (
            round(item["totals"]["energy"] / maximum * 100)
            if maximum > 0 else 0
        )
        for key in keys:
            item["totals"][key] = round(item["totals"][key], 1)

    return result


def meal_templates(db_engine=None):
    selected_engine = (
        food.engine if db_engine is None else db_engine
    )
    init_schema(selected_engine)
    with selected_engine.connect() as db:
        records = db.execute(text("""
            SELECT t.id, t.name,
                   COUNT(i.id) AS item_count
            FROM tracker_food_meal_templates t
            JOIN tracker_food_meal_template_items i
                ON i.template_id=t.id
            GROUP BY t.id, t.name
            ORDER BY t.id DESC
            LIMIT 30
        """)).mappings().all()
    return [dict(row) for row in records]


@router.post("/food/template/save")
async def save_meal_template(request: Request):
    init_schema()
    form = await request.form()

    day = selected_day(form.get("day"))
    meal = str(form.get("meal", ""))
    name = str(form.get("name", "")).strip()[:80]

    if meal not in MEALS:
        raise HTTPException(422, "Select a valid meal")
    if not name:
        raise HTTPException(422, "Template name required")

    with food.engine.begin() as db:
        entries = db.execute(text("""
            SELECT e.product_id, e.servings, e.meal
            FROM tracker_food_entries e
            WHERE e.eaten_on=:day AND e.meal=:meal
            ORDER BY e.id
            LIMIT 31
        """), {
            "day": day,
            "meal": meal,
        }).all()

        if not entries:
            raise HTTPException(
                422, "No logged foods in the selected meal"
            )
        if len(entries) > 30:
            raise HTTPException(
                422, "Meal templates support up to 30 foods"
            )

        result = db.execute(text("""
            INSERT INTO tracker_food_meal_templates(name)
            VALUES (:name)
        """), {"name": name})

        template_id = result.lastrowid

        for product_id, servings, stored_meal in entries:
            db.execute(text("""
                INSERT INTO tracker_food_meal_template_items
                    (template_id, product_id, servings, meal)
                VALUES (:template, :product, :servings, :meal)
            """), {
                "template": template_id,
                "product": product_id,
                "servings": servings,
                "meal": stored_meal,
            })

    return food_redirect(day, "food-templates")


@router.post("/food/template/{template_id}/log")
async def log_meal_template(template_id: int, request: Request):
    init_schema()
    form = await request.form()
    day = selected_day(form.get("day"))

    with food.engine.begin() as db:
        template = db.execute(text("""
            SELECT id FROM tracker_food_meal_templates
            WHERE id=:id
        """), {"id": template_id}).first()

        if template is None:
            raise HTTPException(404, "Meal template not found")

        items = db.execute(text("""
            SELECT i.product_id, i.servings, i.meal
            FROM tracker_food_meal_template_items i
            JOIN tracker_food_products p
                ON p.id=i.product_id
            WHERE i.template_id=:id
            ORDER BY i.id
        """), {"id": template_id}).all()

        if not items or len(items) > 30:
            raise HTTPException(422, "Invalid meal template")

        for product_id, servings, meal in items:
            if not 0 < servings <= 100 or meal not in MEALS:
                raise HTTPException(422, "Invalid saved meal item")

        for product_id, servings, meal in items:
            db.execute(text("""
                INSERT INTO tracker_food_entries
                    (product_id, eaten_on, meal, servings)
                VALUES (:product, :day, :meal, :servings)
            """), {
                "product": product_id,
                "day": day,
                "meal": meal,
                "servings": servings,
            })

    return food_redirect(day, "food-recorded")
