"""Release 379: weekly nutrient coverage and safe target comparisons."""

import csv
import io
import json
from datetime import date, timedelta

from fastapi import Depends, APIRouter, HTTPException, Request
from fastapi.responses import Response, RedirectResponse
from sqlalchemy import text

from . import food
from .food_quick375 import selected_day
from .food_review378 import safe_csv_cell

from ..food_storage_guard391 import require_food_storage391
from ..food_engine392 import get_food_engine392

router = APIRouter(
    dependencies=[Depends(require_food_storage391)]
)


def week_details(day, db_engine=None):
    """Seven calendar days, retaining missing nutrient information."""
    end = date.fromisoformat(selected_day(day))
    start = end - timedelta(days=6)

    food.init_food_schema()

    selected_engine = (
        db_engine if db_engine is not None else food.engine
    )
    with selected_engine.connect() as db:
        entries = db.execute(text("""
            SELECT e.eaten_on, e.servings, p.nutrients
            FROM tracker_food_entries e
            JOIN tracker_food_products p ON p.id=e.product_id
            WHERE e.eaten_on BETWEEN :start AND :end
        """), {
            "start": start.isoformat(),
            "end": end.isoformat(),
        }).all()

        targets = dict(db.execute(text("""
            SELECT nutrient, value FROM tracker_food_targets
        """)).all())

    days = {}

    for offset in range(7):
        current = start + timedelta(days=offset)
        stamp = current.isoformat()

        days[stamp] = {
            "date": stamp,
            "foods": 0,
            "totals": {key: 0.0 for key in food.NUTRIENTS},
            "reported": {key: 0 for key in food.NUTRIENTS},
        }

    for eaten_on, servings, packed in entries:
        item = days[eaten_on]
        item["foods"] += 1

        nutrient_values = json.loads(packed)

        for key in food.NUTRIENTS:
            raw = nutrient_values.get(key)

            if raw is None:
                continue

            item["reported"][key] += 1
            item["totals"][key] += (
                food.to_float(raw) * servings
            )

    summaries = []

    for key, (label, unit) in food.NUTRIENTS.items():
        logged_days = 0
        complete_days = 0
        observed_days = 0
        observed_total = 0.0
        complete_total = 0.0
        below = 0
        above = 0
        at = 0

        target = targets.get(key)

        for item in days.values():
            if item["foods"] == 0:
                continue

            logged_days += 1
            observed = item["reported"][key]

            if observed > 0:
                observed_days += 1
                observed_total += item["totals"][key]

            if observed != item["foods"]:
                continue

            complete_days += 1
            amount = item["totals"][key]
            complete_total += amount

            if target is not None:
                if amount < target:
                    below += 1
                elif amount > target:
                    above += 1
                else:
                    at += 1

        summaries.append({
            "key": key,
            "label": label,
            "unit": unit,
            "logged_days": logged_days,
            "complete_days": complete_days,
            "observed_days": observed_days,
            "observed_average": (
                round(observed_total / observed_days, 2)
                if observed_days else None
            ),
            "complete_average": (
                round(complete_total / complete_days, 2)
                if complete_days else None
            ),
            "target": target,
            "below": below,
            "above": above,
            "at": at,
        })

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": list(days.values()),
        "nutrients": summaries,
    }


@router.get("/food/weekly.csv")
def weekly_csv(
    day: str,
    db_engine=Depends(get_food_engine392),
):
    review = week_details(day, db_engine=db_engine)

    output = io.StringIO(newline="")
    writer = csv.writer(output)

    header = ["Date", "Logged Foods"]

    for key, (label, unit) in food.NUTRIENTS.items():
        header.extend([
            f"{label} ({unit})",
            f"{label} Reported Foods",
            f"{label} Complete",
        ])

    writer.writerow(header)

    for item in review["days"]:
        row = [
            safe_csv_cell(item["date"]),
            item["foods"],
        ]

        for key in food.NUTRIENTS:
            reported = item["reported"][key]
            complete = (
                item["foods"] > 0
                and reported == item["foods"]
            )

            row.extend([
                (
                    round(item["totals"][key], 3)
                    if reported else ""
                ),
                reported,
                "yes" if complete else "no",
            ])

        writer.writerow(row)

    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                'attachment; filename="tracker-food-week-'
                + review["end"] + '.csv"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
