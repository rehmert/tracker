"""Release 375: reusable products and mobile-first quick food logging."""
from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from ..db import engine
from .food import init_food_schema, to_float

router = APIRouter()

MEALS = frozenset(("Breakfast", "Lunch", "Dinner", "Snack"))


def selected_day(raw):
    try:
        return date.fromisoformat(str(raw)).isoformat()
    except (TypeError, ValueError):
        raise HTTPException(422, "Invalid food journal date")


def food_redirect(day):
    return RedirectResponse(
        "/food?" + urlencode({"day": day}), status_code=303
    )


def saved_foods():
    init_food_schema()
    with engine.connect() as db:
        favorites = db.execute(text("""
            SELECT p.id, p.name, p.serving_description,
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
            FROM tracker_food_favorites f
            JOIN tracker_food_products p ON p.id=f.product_id
            ORDER BY f.created_at DESC, p.id DESC
            LIMIT 24
        """)).mappings().all()

        recent = db.execute(text("""
            SELECT p.id, p.name, p.serving_description,
                   e.meal, e.servings
            FROM tracker_food_entries e
            JOIN tracker_food_products p ON p.id=e.product_id
            WHERE e.id = (
                SELECT MAX(x.id) FROM tracker_food_entries x
                WHERE x.product_id=e.product_id
            )
            ORDER BY e.id DESC
            LIMIT 12
        """)).mappings().all()

    return [dict(x) for x in favorites], [dict(x) for x in recent]


@router.post("/food/quick/{product_id}")
async def quick_log(product_id: int, request: Request):
    init_food_schema()
    form = await request.form()
    day = selected_day(form.get("day"))
    servings = to_float(form.get("servings"))
    if not 0 < servings <= 100:
        raise HTTPException(422, "Servings must be 0–100, excluding zero")
    meal = str(form.get("meal", "Snack"))
    if meal not in MEALS:
        raise HTTPException(422, "Invalid meal")

    with engine.begin() as db:
        product = db.execute(
            text("SELECT id FROM tracker_food_products WHERE id=:id"),
            {"id": product_id},
        ).first()
        if product is None:
            raise HTTPException(404, "Saved food no longer exists")
        db.execute(text("""
            INSERT INTO tracker_food_entries
                (product_id, eaten_on, meal, servings)
            VALUES (:id, :day, :meal, :servings)
        """), {
            "id": product_id, "day": day,
            "meal": meal, "servings": servings,
        })

    return food_redirect(day)


@router.post("/food/favorite/{product_id}")
async def toggle_favorite(product_id: int, request: Request):
    init_food_schema()
    form = await request.form()
    day = selected_day(form.get("day"))

    with engine.begin() as db:
        exists = db.execute(
            text("SELECT id FROM tracker_food_products WHERE id=:id"),
            {"id": product_id},
        ).first()
        if exists is None:
            raise HTTPException(404, "Saved food no longer exists")

        favorite = db.execute(text("""
            SELECT product_id FROM tracker_food_favorites
            WHERE product_id=:id
        """), {"id": product_id}).first()

        if favorite:
            db.execute(text("""
                DELETE FROM tracker_food_favorites
                WHERE product_id=:id
            """), {"id": product_id})
        else:
            db.execute(text("""
                INSERT INTO tracker_food_favorites(product_id)
                VALUES (:id)
            """), {"id": product_id})

    return food_redirect(day)
