"""Unified read-only inventory planning dashboard."""
import csv
import io
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from ..db import get_db
from ..templating import render
from .scheduled_forecast import build_schedule, HORIZONS
from .forecast_audit import audit_rows

router = APIRouter()

def build_planning(db):
    scheduled, warnings = build_schedule(db)
    averages = audit_rows(db, days=28)
    avg_index = {(r["compound"], r["unit"]): r for r in averages}
    scheduled_keys = set()
    rows = []
    for r in scheduled:
        key = (r["compound"], r["unit"])
        scheduled_keys.add(key)
        avg = avg_index.get(key)
        rows.append({
            "compound": r["compound"], "unit": r["unit"],
            "protocols": r["protocols"], "items": r["items"],
            "available": r["available"],
            "occurrences": r["counts"],
            "scheduled": r["demands"], "flags": r["flags"],
            "average28": avg["demand"] if avg else None,
            "average_flag": avg["flag"] if avg else "Different unit basis",
        })
    unmatched = [r for r in averages if (r["compound"], r["unit"]) not in scheduled_keys]
    return rows, warnings, unmatched



# RELEASE_169_176
# Read-only expiration exposure integration.

from .expiry_exposure import exposure_rows as _expiry_exposure_rows


def _planning_expiry_comparison(db, scheduled_rows, horizons):
    """
    Compare current recorded expiration exposure with scheduled
    demand, without assuming consumption order.

    Stock approaching expiration is NOT automatically considered
    unavailable. No inventory transactions are performed.
    """

    expiry_rows = _expiry_exposure_rows(db)

    expiry_index = {
        (str(row["compound"]), str(row["unit"])): row
        for row in expiry_rows
    }

    comparisons = []
    matched = set()

    for scheduled in scheduled_rows:

        compound = str(scheduled["compound"])
        unit = str(scheduled["unit"])

        key = (compound, unit)

        exposure = expiry_index.get(key)

        if exposure is not None:
            matched.add(key)

        current_stock = scheduled.get("available")

        horizon_rows = []

        for days in horizons:

            demand = scheduled.get(
                "scheduled", {}
            ).get(days)

            at_risk = (
                exposure.get("expiring", {}).get(days, 0)
                if exposure is not None
                else None
            )

            missing_dates = (
                exposure.get("unknown_dates", 0)
                if exposure is not None
                else None
            )

            # Do not assume that at-risk inventory will expire
            # before it can be consumed.
            #
            # Instead, calculate a conservative planning scenario
            # where all inventory with a date within the horizon
            # is excluded.
            #
            # This is a scenario, not a prediction.

            conservative_stock = None
            conservative_gap = None

            if (
                current_stock is not None
                and at_risk is not None
            ):

                try:
                    conservative_stock = max(
                        0.0,
                        float(current_stock) - float(at_risk)
                    )

                    if demand is not None:
                        conservative_gap = (
                            conservative_stock - float(demand)
                        )

                except (
                    TypeError,
                    ValueError,
                    OverflowError
                ):
                    conservative_stock = None
                    conservative_gap = None

            horizon_rows.append({
                "days": days,
                "demand": demand,
                "at_risk": at_risk,
                "conservative_stock": conservative_stock,
                "conservative_gap": conservative_gap,
                "missing_dates": missing_dates,
            })

        comparisons.append({
            "compound": compound,
            "unit": unit,
            "current_stock": current_stock,
            "matched": exposure is not None,
            "horizons": horizon_rows,
        })

    unmatched = [
        row
        for row in expiry_rows
        if (
            str(row["compound"]),
            str(row["unit"])
        ) not in matched
    ]

    return comparisons, unmatched


@router.get("/planning-hub")
def planning_hub(request: Request, db: Session = Depends(get_db)):
    rows, warnings, unmatched = build_planning(db)
    expiry_comparisons, unmatched_expiry = _planning_expiry_comparison(db, rows, HORIZONS)
    return render(request, "planning_hub.html", rows=rows, warnings=warnings,
                  unmatched=unmatched, horizons=HORIZONS, expiry_comparisons=expiry_comparisons, unmatched_expiry=unmatched_expiry)

@router.get("/planning-hub.csv")
def planning_hub_csv(db: Session = Depends(get_db)):
    rows, warnings, unmatched = build_planning(db)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Compound", "Unit", "Protocols", "Items", "Stock estimate",
                     "Average 28d demand", "Average forecast flag"] +
                    [f"Scheduled {h}d occurrences" for h in HORIZONS] +
                    [f"Scheduled {h}d demand" for h in HORIZONS] +
                    [f"Scheduled {h}d flag" for h in HORIZONS])
    for r in rows:
        name = r["compound"]
        if name.lstrip().startswith(("=", "+", "-", "@")):
            name = "'" + name
        writer.writerow([name, r["unit"], r["protocols"], r["items"],
                         r["available"] if r["available"] is not None else "",
                         r["average28"] if r["average28"] is not None else "",
                         r["average_flag"]] +
                        [r["occurrences"].get(h, 0) for h in HORIZONS] +
                        [r["scheduled"].get(h) if r["scheduled"].get(h) is not None else "" for h in HORIZONS] +
                        [r["flags"].get(h, "") for h in HORIZONS])
    return Response("\ufeff" + stream.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="planning-hub.csv"'})
