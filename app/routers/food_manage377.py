"""Release 377: safe food-entry edits and meal-template management."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from . import food
from .food_quick375 import (
    MEALS,
    food_redirect,
    selected_day,
)
from .food_bundle376 import init_schema

router = APIRouter()


def valid_quantity(raw):
    try:
        value = food.optional_nutrient(raw)
    except HTTPException:
        raise HTTPException(422, "Invalid serving quantity")

    if value is None or not 0 < value <= 100:
        raise HTTPException(
            422,
            "Servings must be greater than zero and at most 100",
        )
    return value


@router.post("/food/entry/{entry_id}/edit")
async def edit_food_entry(entry_id: int, request: Request):
    """Update only date, meal and quantity; never product nutrients."""
    food.init_food_schema()
    form = await request.form()

    day = selected_day(form.get("day"))
    original_day = selected_day(form.get("original_day"))
    servings = valid_quantity(form.get("servings"))
    meal = str(form.get("meal", ""))

    if meal not in MEALS:
        raise HTTPException(422, "Invalid meal")

    with food.engine.begin() as db:
        result = db.execute(text("""
            UPDATE tracker_food_entries
            SET eaten_on=:day, meal=:meal, servings=:servings
            WHERE id=:id AND eaten_on=:original_day
        """), {
            "day": day,
            "meal": meal,
            "servings": servings,
            "id": entry_id,
            "original_day": original_day,
        })

        if result.rowcount != 1:
            raise HTTPException(
                404, "Food entry no longer exists on that day"
            )

    return food_redirect(day, "food-recorded")


@router.post("/food/template/{template_id}/rename")
async def rename_meal_template(
    template_id: int,
    request: Request,
):
    init_schema()
    form = await request.form()

    day = selected_day(form.get("day"))
    name = str(form.get("name", "")).strip()

    if not name or len(name) > 80:
        raise HTTPException(
            422, "Template name must contain 1–80 characters"
        )

    with food.engine.begin() as db:
        result = db.execute(text("""
            UPDATE tracker_food_meal_templates
            SET name=:name
            WHERE id=:id
        """), {
            "name": name,
            "id": template_id,
        })

        if result.rowcount != 1:
            raise HTTPException(
                404, "Meal template not found"
            )

    return food_redirect(day, "food-templates")


@router.post("/food/template/{template_id}/delete")
async def delete_meal_template(
    template_id: int,
    request: Request,
):
    """Delete the template only; historical food entries are preserved."""
    init_schema()
    form = await request.form()

    day = selected_day(form.get("day"))

    with food.engine.begin() as db:
        exists = db.execute(text("""
            SELECT id FROM tracker_food_meal_templates
            WHERE id=:id
        """), {"id": template_id}).first()

        if exists is None:
            raise HTTPException(
                404, "Meal template not found"
            )

        db.execute(text("""
            DELETE FROM tracker_food_meal_template_items
            WHERE template_id=:id
        """), {"id": template_id})

        db.execute(text("""
            DELETE FROM tracker_food_meal_templates
            WHERE id=:id
        """), {"id": template_id})

    return food_redirect(day, "food-templates")
