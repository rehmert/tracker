"""Release 470: authenticated private inventory and food reads.

These functions receive an HTTP Request and resolve its user
through the existing secondary session. They cannot select
an account, path, engine, SQL statement or write permission.

The existing isolated write workers remain unchanged.
"""
import json

from sqlalchemy import text
from fastapi import HTTPException

from .secondary_orm468 import private_orm468
from .worker_food452 import (
    NUTRIENTS, MAX_ROWS, WATER_TARGET_OZ,
    _safe_number452, validate_day452,
)
from .worker_week454 import (
    days454, validate_response454,
)


INVENTORY_COMPOUNDS470 = text("""
    SELECT id,name,category,primary_unit
    FROM compounds
    ORDER BY name COLLATE NOCASE,id
    LIMIT 200
""")

INVENTORY_VIALS470 = text("""
    SELECT v.id,v.compound_id,c.name,v.label,
           v.content_value,v.content_unit,v.status,v.form
    FROM vials AS v
    JOIN compounds AS c ON c.id=v.compound_id
    ORDER BY v.id DESC
    LIMIT 200
""")

FOOD_ENTRIES470 = text("""
    SELECT substr(p.name,1,160),
           substr(e.meal,1,40),
           e.servings,p.nutrients
    FROM tracker_food_entries AS e
    JOIN tracker_food_products AS p ON p.id=e.product_id
    WHERE e.eaten_on=:day
    ORDER BY e.id DESC
    LIMIT :limit
""")

WATER_TOTAL470 = text("""
    SELECT COALESCE(SUM(ounces),0)
    FROM tracker_water_entries
    WHERE logged_on=:day
""")


def private_inventory_orm470(request):
    with private_orm468(request) as (scope, db):
        compounds = [
            {
                "id": row[0],
                "name": row[1],
                "category": row[2],
                "primary_unit": row[3],
            }
            for row in db.execute(INVENTORY_COMPOUNDS470)
        ]

        vials = [
            {
                "id": row[0],
                "compound_id": row[1],
                "compound": row[2],
                "label": row[3],
                "content_value": row[4],
                "content_unit": row[5],
                "status": row[6],
                "form": row[7],
            }
            for row in db.execute(INVENTORY_VIALS470)
        ]

    if (
        scope.user_id <= 1
        or len(compounds) > 200
        or len(vials) > 200
    ):
        raise HTTPException(
            503, "Invalid private inventory response"
        )

    return {
        "mode": "private-inventory-orm470",
        "status": "inventory",
        "user_id": scope.user_id,
        "compounds": compounds,
        "vials": vials,
        "read_only": True,
    }


def _food_day_from_db470(db, uid, day):
    day = validate_day452(day)

    rows = db.execute(
        FOOD_ENTRIES470,
        {"day": day, "limit": MAX_ROWS + 1},
    ).all()

    water = db.execute(
        WATER_TOTAL470, {"day": day}
    ).scalar_one()

    items = []
    totals = {key: 0.0 for key in NUTRIENTS}
    coverage = {key: 0 for key in NUTRIENTS}

    for name, meal, servings, raw in rows[:MAX_ROWS]:
        quantity = _safe_number452(servings)

        if (
            quantity is None
            or quantity == 0
            or quantity > 100
        ):
            raise RuntimeError(
                "Invalid recorded serving count"
            )

        try:
            nutrients = json.loads(raw)
        except (ValueError, TypeError):
            raise RuntimeError(
                "Invalid recorded nutrients"
            ) from None

        if type(nutrients) is not dict:
            raise RuntimeError(
                "Invalid nutrient record"
            )

        item = {
            "name": str(name or "")[:160],
            "meal": str(meal or "Snack")[:40],
            "servings": quantity,
        }

        for key in NUTRIENTS:
            per_serving = _safe_number452(
                nutrients.get(key)
            )

            if per_serving is None:
                item[key] = None
                continue

            amount = round(
                per_serving * quantity, 2
            )

            if _safe_number452(amount) is None:
                raise RuntimeError(
                    "Invalid calculated nutrient amount"
                )

            item[key] = amount
            totals[key] += amount
            coverage[key] += 1

        # Preserve the calculated entry in the daily report.
        # Nutrient totals alone are not sufficient: the
        # journal renderer and weekly coverage checks need
        # the individual entries as well.
        items.append(item)

    water_value = _safe_number452(water)

    if water_value is None:
        raise RuntimeError(
            "Invalid recorded water total"
        )

    if any(
        _safe_number452(value) is None
        for value in totals.values()
    ):
        raise RuntimeError(
            "Invalid recorded nutrient totals"
        )

    return {
        "mode": "offline-food-day452",
        "user_id": uid,
        "day": day,
        "items": items,
        "totals": {
            key: round(value, 2)
            for key, value in totals.items()
        },
        "coverage": coverage,
        "water_oz": round(water_value, 2),
        "water_target_oz": WATER_TARGET_OZ,
        "has_more": len(rows) > MAX_ROWS,
        "login_enabled": False,
        "http_listener_started": False,
    }


def private_food_day_orm470(request, day):
    day = validate_day452(day)

    with private_orm468(request) as (scope, db):
        report = _food_day_from_db470(
            db, scope.user_id, day
        )

    if report["user_id"] != scope.user_id:
        raise HTTPException(
            503, "Private food identity mismatch"
        )

    return report


def private_food_week_orm470(request, end_day):
    expected = days454(end_day)

    # Reuse one verified read-only connection for
    # all seven days, rather than launching workers.
    with private_orm468(request) as (scope, db):
        reports = [
            _food_day_from_db470(
                db, scope.user_id, day
            )
            for day in expected
        ]

    envelope = {
        "mode": "offline-food-week454",
        "user_id": scope.user_id,
        "end_day": end_day,
        "reports": reports,
    }

    # Preserve the existing strict weekly contract.
    return validate_response454(
        envelope, scope.user_id, end_day
    )
