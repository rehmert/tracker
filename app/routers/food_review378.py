"""Release 378: immutable nutrition corrections, meal totals and CSV."""
import csv
import io
import json
import re
from collections import OrderedDict

from fastapi import Depends, APIRouter, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import text

from . import food
from .food_quick375 import selected_day, food_redirect, MEALS

from ..food_storage_guard391 import require_food_storage391

router = APIRouter(
    dependencies=[Depends(require_food_storage391)]
)

MACROS = ("energy", "proteins", "carbohydrates", "fat")
MEAL_ORDER = ("Breakfast", "Lunch", "Dinner", "Snack")


def meal_summary(day):
    food.init_food_schema()
    result = OrderedDict()

    for meal in MEAL_ORDER:
        result[meal] = {
            "name": meal,
            "count": 0,
            "totals": {key: 0.0 for key in MACROS},
            "reported": {key: 0 for key in MACROS},
        }

    with food.engine.connect() as db:
        rows = db.execute(text("""
            SELECT e.meal, e.servings, p.nutrients
            FROM tracker_food_entries e
            JOIN tracker_food_products p ON p.id=e.product_id
            WHERE e.eaten_on=:day
        """), {"day": day}).all()

    for meal, servings, packed in rows:
        if meal not in result:
            continue

        item = result[meal]
        item["count"] += 1
        values = json.loads(packed)

        for key in MACROS:
            if values.get(key) is not None:
                item["reported"][key] += 1
                item["totals"][key] += (
                    food.to_float(values[key]) * servings
                )

    for item in result.values():
        for key in MACROS:
            item["totals"][key] = round(
                item["totals"][key], 1
            )

    return list(result.values())


@router.post("/food/entry/{entry_id}/nutrition")
async def correct_nutrition(entry_id: int, request: Request):
    """Copy-on-write: only this logged entry uses the corrected product."""
    food.init_food_schema()
    form = await request.form()

    day = selected_day(form.get("day"))
    name = str(form.get("name", "")).strip()
    description = str(form.get("serving_description", "")).strip()

    if not name or len(name) > 160:
        raise HTTPException(422, "Food name must be 1–160 characters")

    if not description or len(description) > 80:
        raise HTTPException(
            422, "Serving description must be 1–80 characters"
        )

    values = {
        key: food.optional_nutrient(form.get(key))
        for key in food.NUTRIENTS
    }

    with food.engine.begin() as db:
        entry = db.execute(text("""
            SELECT e.product_id, p.barcode, p.source
            FROM tracker_food_entries e
            JOIN tracker_food_products p ON p.id=e.product_id
            WHERE e.id=:id AND e.eaten_on=:day
        """), {"id": entry_id, "day": day}).first()

        if entry is None:
            raise HTTPException(404, "Food entry not found")

        product_id, barcode, old_source = entry
        source = ("Corrected: " + str(old_source))[:80]
        packed = json.dumps(values)

        # Preserve the existing product and all references to it.
        # A snapshot is associated only with this entry.
        inserted = db.execute(text("""
            INSERT INTO tracker_food_products
                (barcode, name, serving_description, nutrients, source)
            VALUES (:barcode, :name, :description, :nutrients, :source)
        """), {
            "barcode": barcode,
            "name": name,
            "description": description,
            "nutrients": packed,
            "source": source,
        })

        updated = db.execute(text("""
            UPDATE tracker_food_entries
            SET product_id=:product
            WHERE id=:id AND eaten_on=:day AND product_id=:old
        """), {
            "product": inserted.lastrowid,
            "id": entry_id,
            "day": day,
            "old": product_id,
        })

        if updated.rowcount != 1:
            raise HTTPException(
                409, "Food entry changed; reload and retry"
            )

    return food_redirect(day, "food-recorded")


def safe_csv_cell(value):
    """Prevent spreadsheet formula execution in text fields."""
    value = str(value or "")
    if value and value.lstrip().startswith(
        ("=", "+", "-", "@", "\t", "\r")
    ):
        return "'" + value
    return value


@router.get("/food/export.csv")
def export_food_csv(day: str):
    day = selected_day(day)
    food.init_food_schema()

    with food.engine.connect() as db:
        records = db.execute(text("""
            SELECT e.id, e.eaten_on, e.meal, e.servings,
                   p.name, p.barcode, p.serving_description,
                   p.source, p.nutrients
            FROM tracker_food_entries e
            JOIN tracker_food_products p ON p.id=e.product_id
            WHERE e.eaten_on=:day
            ORDER BY e.id
        """), {"day": day}).mappings().all()

    out = io.StringIO(newline="")
    writer = csv.writer(out)

    headers = [
        "Entry ID", "Date", "Meal", "Food", "Barcode",
        "Serving Basis", "Servings", "Source"
    ]

    for key, (label, unit) in food.NUTRIENTS.items():
        headers.append(f"{label} ({unit})")

    writer.writerow(headers)

    for entry in records:
        nutrients = json.loads(entry["nutrients"])
        row = [
            entry["id"],
            entry["eaten_on"],
            entry["meal"],
            safe_csv_cell(entry["name"]),
            safe_csv_cell(entry["barcode"]),
            safe_csv_cell(entry["serving_description"]),
            entry["servings"],
            safe_csv_cell(entry["source"]),
        ]

        for key in food.NUTRIENTS:
            value = nutrients.get(key)
            row.append(
                "" if value is None
                else round(
                    food.to_float(value) * entry["servings"], 3
                )
            )

        writer.writerow(row)

    content = "\ufeff" + out.getvalue()

    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                f'attachment; filename="tracker-food-{day}.csv"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
