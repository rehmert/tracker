"""Release 674 compact daily summary from existing scoped records.

No writes and no additional tables. Food is optional for authorized workspaces.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from .models import Vial
from .workout_models654 import WorkoutSession654, WorkoutSet654


def snapshot674(db: Session, today: date, food_engine=None):
    start = datetime.combine(today, datetime.min.time())
    end = start + timedelta(days=1)
    workout_today = db.scalar(
        select(func.count(WorkoutSession654.id))
        .where(WorkoutSession654.started_at >= start, WorkoutSession654.started_at < end)
    ) or 0
    latest_session = db.scalar(
        select(WorkoutSession654).order_by(WorkoutSession654.started_at.desc(),
                                           WorkoutSession654.id.desc()).limit(1)
    )
    sets_today = db.scalar(
        select(func.count(WorkoutSet654.id))
        .join(WorkoutSession654, WorkoutSet654.session_id == WorkoutSession654.id)
        .where(WorkoutSession654.started_at >= start, WorkoutSession654.started_at < end)
    ) or 0
    attention_vials = db.scalar(
        select(func.count(Vial.id)).where(
            Vial.status.in_(("sealed", "in_use")),
            Vial.closed_on.is_(None),
            (
                ((Vial.expires_on.is_not(None)) & (Vial.expires_on < today)) |
                ((Vial.beyond_use_on.is_not(None)) & (Vial.beyond_use_on < today))
            ),
        )
    ) or 0
    food = dict(available=False, count=0, calories=None, coverage="Not available")
    if food_engine is not None:
        with food_engine.connect() as conn:
            if {"tracker_food_entries", "tracker_food_products"}.issubset(
                    inspect(conn).get_table_names()):
                rows = conn.execute(text(
                    "SELECT p.nutrients,e.servings FROM tracker_food_entries e "
                    "JOIN tracker_food_products p ON p.id=e.product_id WHERE e.eaten_on=:day"
                ), {"day":today.isoformat()}).all()
                from .routers.food import to_float
                import json
                energy = 0.0
                known = 0
                for nutrient_json, servings in rows:
                    try:
                        value = json.loads(nutrient_json).get("energy")
                    except (ValueError, TypeError, AttributeError):
                        value = None
                    if value is not None:
                        known += 1
                        energy += to_float(value) * servings
                food = dict(available=True, count=len(rows),
                            calories=round(energy) if known else None,
                            coverage=("Complete" if known == len(rows) else
                                      f"Partial: {known} of {len(rows)} foods"))
    return dict(
        workout_today=workout_today,
        sets_today=sets_today,
        last_workout=latest_session,
        inventory_attention=attention_vials,
        food=food,
    )
