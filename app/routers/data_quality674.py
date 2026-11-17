"""Release 674: scoped, read-only cross-module quality review.

Rules identify incomplete records only; they are not clinical interpretations.
Food checks run only when the existing food-storage guard permits access.
"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func, text, inspect
from sqlalchemy.orm import Session

from ..models import Coa, Purchase, Vial
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..workout_models654 import WorkoutEquipment654, WorkoutSet654
from ..workout_models668 import WorkoutSetCorrection668

router = APIRouter()


def quality_summary674(db: Session, food_engine=None):
    """Limit examples, count reliably, avoid schema writes or record edits."""
    issues = []
    coas = list(db.scalars(select(Coa).order_by(Coa.id.desc())))
    for coa in coas:
        missing = []
        if not (coa.lab_name or "").strip():
            missing.append("laboratory")
        if coa.tested_on is None:
            missing.append("test date")
        if not (coa.original_name or "").strip() and not coa.attachments:
            missing.append("document")
        if missing:
            issues.append(dict(kind="COA", label=f"COA #{coa.id}",
                               detail="Missing " + ", ".join(missing),
                               href=f"/coas/{coa.id}"))
    purchases = list(db.scalars(select(Purchase).order_by(Purchase.id.desc())))
    for order in purchases:
        if not order.vials and not order.supplies:
            issues.append(dict(kind="Purchase", label=f"Order #{order.id} — {order.vendor}",
                               detail="Order has no recorded inventory",
                               href=f"/purchases/{order.id}"))
    machines = list(db.scalars(select(WorkoutEquipment654).order_by(WorkoutEquipment654.id)))
    for machine in machines:
        if not (machine.qr_value or "").strip() and machine.kind in ("selectorized", "plate_loaded"):
            issues.append(dict(kind="Workout", label=machine.name,
                               detail="Machine has no QR mapping",
                               href="/workouts"))
    food_status = "Food records not assessed"
    if food_engine is not None:
        with food_engine.connect() as conn:
            tables = set(inspect(conn).get_table_names())
            if {"tracker_food_entries", "tracker_food_products"}.issubset(tables):
                food_status = "Food records checked"
                records = conn.execute(text(
                    "SELECT p.id, p.name, p.nutrients FROM tracker_food_products p "
                    "WHERE EXISTS(SELECT 1 FROM tracker_food_entries e WHERE e.product_id=p.id) "
                    "ORDER BY p.id DESC LIMIT 1000"
                )).mappings().all()
                # Explicit null means missing; numeric zero remains known.
                for row in records:
                    try:
                        nutrients = json.loads(row["nutrients"])
                    except (ValueError, TypeError):
                        nutrients = {}
                    if any(nutrients.get(key) is None for key in ("energy", "proteins", "carbohydrates", "fat")):
                        issues.append(dict(kind="Food", label=row["name"],
                                           detail="One or more core nutrients are unreported",
                                           href=f"/food/saved/{row['id']}/edit"))
            else:
                food_status = "No food records initialized"
    counts = {}
    for item in issues:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    return dict(issues=issues, counts=counts, food_status=food_status,
                total=len(issues), limited=False)


@router.get("/data-quality")
def data_quality674(request: Request, db: Session = Depends(get_scoped_db390)):
    food_engine = None
    try:
        from ..food_engine392 import get_food_engine392
        food_engine = get_food_engine392(request)
    except Exception as exc:
        # Read-only dashboard must remain accessible when Food is disabled,
        # but do not swallow unexpected database errors after authorization.
        from fastapi import HTTPException
        if not isinstance(exc, HTTPException) or exc.status_code not in (403, 503):
            raise
    report = quality_summary674(db, food_engine)
    return render(request, "data_quality674.html", report=report,
                  today=datetime.now().date())
