"""Release 629: review and explicitly consolidate equivalent saved foods.

The read-only comparison shows all supported nutrients per serving.
A merge is allowed only when the complete nutrient payload, normalized name,
barcode and serving size match. It preserves recorded nutrient totals and
updates all known references transactionally.
"""
from collections import defaultdict
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from ..food_storage_guard391 import require_food_storage391
from ..food_read_engine406 import get_food_read_engine406
from ..templating import render
from . import food, food_bundle376

router = APIRouter(dependencies=[Depends(require_food_storage391)])
MAX_PRODUCTS = 5000
MAX_MERGE = 30


def normalize629(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def nutrient_key629(raw):
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError("Saved food has invalid nutrient data") from None
    if type(parsed) is not dict:
        raise ValueError("Saved food nutrients must be an object")
    # A structural comparison preserves unknown versus explicit zero,
    # nonstandard fields and corrections made after a food was logged.
    return json.dumps(parsed, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def compatible_key629(row):
    return (normalize629(row["name"]),
            normalize629(row["serving_description"]),
            normalize629(row["barcode"]),
            nutrient_key629(row["nutrients"]))


def _fetch_products629(db):
    return db.execute(text("""
        SELECT p.id, p.name, p.barcode, p.serving_description,
               p.nutrients, p.source,
               (SELECT COUNT(*) FROM tracker_food_entries e
                WHERE e.product_id=p.id) AS log_count,
               (SELECT COUNT(*) FROM tracker_food_meal_template_items i
                WHERE i.product_id=p.id) AS template_count,
               (SELECT COUNT(*) FROM tracker_food_favorites f
                WHERE f.product_id=p.id) AS favorite_count
        FROM tracker_food_products p
        ORDER BY p.name COLLATE NOCASE, p.id
        LIMIT :limit
    """), {"limit": MAX_PRODUCTS + 1}).mappings().all()


def duplicate_groups629(db_engine):
    food_bundle376.init_schema(db_engine)
    with db_engine.connect() as db:
        rows = [dict(x) for x in _fetch_products629(db)]
    limited = len(rows) > MAX_PRODUCTS
    rows = rows[:MAX_PRODUCTS]
    groups = defaultdict(list)
    for row in rows:
        key = normalize629(row["name"])
        if not key:
            key = f"unnamed:{row['id']}"
        try:
            parsed = json.loads(row["nutrients"])
            if type(parsed) is not dict:
                raise ValueError("not an object")
            row["measurements"] = {
                name: parsed.get(name)
                for name in food.NUTRIENTS
            }
            row["match_key"] = compatible_key629(row)
            row["valid_nutrients"] = True
        except (TypeError, ValueError):
            row["measurements"] = {
                name: None for name in food.NUTRIENTS
            }
            row["match_key"] = None
            row["valid_nutrients"] = False
        groups[key].append(row)

    result = []
    for entries in groups.values():
        if len(entries) < 2:
            continue
        exact = defaultdict(list)
        for item in entries:
            if item["match_key"] is not None:
                exact[item["match_key"]].append(item)
        compatible = [group for group in exact.values() if len(group) > 1]
        differing = [
            nutrient for nutrient in food.NUTRIENTS
            if len({
                json.dumps(item["measurements"][nutrient],
                           sort_keys=True, default=str)
                for item in entries
            }) > 1
        ]
        result.append({
            "name": entries[0]["name"],
            "versions": entries,
            "equivalent_sets": compatible,
            "different_nutrients": differing,
            "different_values": len(exact) != 1 or any(
                not item["valid_nutrients"] for item in entries
            ),
        })
    result.sort(key=lambda group: normalize629(group["name"]))
    return {"groups": result, "examined": len(rows), "truncated": limited}


def merge_equivalent629(db_engine, keep_id, remove_ids):
    if (type(keep_id) is not int or keep_id < 1
            or type(remove_ids) is not list
            or not 1 <= len(remove_ids) <= MAX_MERGE
            or any(type(value) is not int or value < 1
                   for value in remove_ids)
            or len(set(remove_ids)) != len(remove_ids)
            or keep_id in remove_ids):
        raise ValueError("Invalid consolidation selection")

    food_bundle376.init_schema(db_engine)
    with db_engine.begin() as db:
        ids = [keep_id, *remove_ids]
        records = []
        for value in ids:
            row = db.execute(text("""
                SELECT id,name,barcode,serving_description,nutrients
                FROM tracker_food_products WHERE id=:id
            """), {"id": value}).mappings().first()
            if row is None:
                raise ValueError("Saved food was changed or removed")
            records.append(row)
        try:
            keys = [compatible_key629(row) for row in records]
        except ValueError:
            raise ValueError("Invalid nutrient data; cannot merge") from None
        if any(key != keys[0] for key in keys[1:]):
            raise ValueError(
                "Different nutrients, serving sizes or barcodes: "
                "review these versions instead of merging"
            )

        # All links are moved before removing old product rows, atomically.
        for old_id in remove_ids:
            db.execute(text("""
                INSERT OR IGNORE INTO tracker_food_favorites(product_id)
                SELECT :keep FROM tracker_food_favorites
                WHERE product_id=:old
            """), {"keep": keep_id, "old": old_id})
            db.execute(text("""
                DELETE FROM tracker_food_favorites WHERE product_id=:old
            """), {"old": old_id})
            db.execute(text("""
                UPDATE tracker_food_entries SET product_id=:keep
                WHERE product_id=:old
            """), {"keep": keep_id, "old": old_id})
            db.execute(text("""
                UPDATE tracker_food_meal_template_items SET product_id=:keep
                WHERE product_id=:old
            """), {"keep": keep_id, "old": old_id})
            db.execute(text("""
                DELETE FROM tracker_food_products WHERE id=:old
            """), {"old": old_id})
    return len(remove_ids)


@router.get("/food/duplicates")
def review_duplicate_foods629(
    request: Request,
    merged: int = 0,
    db_engine=Depends(get_food_read_engine406),
):
    report = duplicate_groups629(db_engine)
    return render(
        request, "food_duplicates629.html",
        **report, nutrients=food.NUTRIENTS,
        merged=max(0, min(merged, MAX_MERGE)),
    )


@router.post("/food/duplicates/merge")
async def merge_duplicate_foods629(
    request: Request,
    db_engine=Depends(get_food_read_engine406),
):
    form = await request.form()
    allowed_fields = {"keep_id", "remove_id", "csrf_token"}
    if (not {"keep_id", "remove_id"} <= set(form)
        or not set(form) <= allowed_fields
        or len(form.getlist("csrf_token")) > 1
        or len(form.getlist("keep_id")) != 1
        or not 1 <= len(form.getlist("remove_id")) <= MAX_MERGE
    ):
        raise HTTPException(422, "Invalid duplicate merge form")
    try:
        ids = [int(value) for value in form.getlist("remove_id")]
        keep_id = int(form["keep_id"])
        merged = merge_equivalent629(db_engine, keep_id, ids)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return RedirectResponse(
        f"/food/duplicates?merged={merged}",
        status_code=303,
    )
