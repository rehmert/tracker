
"""Release 201-208: read-only inventory planning priorities."""

import csv
import io
from datetime import date
from math import isfinite

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..templating import render
from .fefo_forecast import build_fefo, HORIZONS

router = APIRouter()


def finite_number(value):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return result if isfinite(result) else 0.0


def priority_rows(
    rows,
    horizon=28,
    compound="",
    category="all",
):
    """Transform existing FEFO results without changing them."""

    if horizon not in HORIZONS:
        raise ValueError("Unsupported forecast horizon")

    needle = compound.strip().casefold()
    results = []

    for row in rows:
        name = str(row["compound"])
        unit = str(row["unit"])

        if needle and needle not in name.casefold():
            continue

        forecast = row["horizons"][horizon]

        shortage = max(
            0.0,
            finite_number(forecast.get("shortage")),
        )
        expired = max(
            0.0,
            finite_number(forecast.get("expired")),
        )
        demand = max(
            0.0,
            finite_number(forecast.get("demand")),
        )
        allocated = max(
            0.0,
            finite_number(forecast.get("consumed")),
        )
        remaining = max(
            0.0,
            finite_number(forecast.get("remaining")),
        )
        unknown = max(
            0.0,
            finite_number(row.get("unknown_stock")),
        )

        incomplete = bool(row.get("incomplete"))
        first_shortage = forecast.get("first_shortage")

        if shortage > 1e-9:
            status = "Shortage"
            rank = 0
        elif expired > 1e-9:
            status = "Expiration exposure"
            rank = 1
        elif incomplete or unknown > 1e-9:
            status = "Data review"
            rank = 2
        else:
            status = "No identified issue"
            rank = 3

        if category == "shortage" and shortage <= 1e-9:
            continue
        if category == "expiration" and expired <= 1e-9:
            continue
        if category == "review" and not (
            incomplete or unknown > 1e-9
        ):
            continue

        # Demand and available stock are already in the
        # compound's reporting unit, as returned by FEFO.
        #
        # This is a simple demand-rate indicator, not a
        # date-accurate exhaustion forecast.
        #
        # A shortage date comes only from the FEFO engine.

        daily_demand = demand / horizon

        coverage = (
            (allocated + remaining) / daily_demand
            if daily_demand > 0
            else None
        )

        results.append({
            "compound": name,
            "unit": unit,
            "status": status,
            "rank": rank,
            "dated_stock": finite_number(
                row.get("dated_stock")
            ),
            "unknown_stock": unknown,
            "demand": demand,
            "allocated": allocated,
            "shortage": shortage,
            "expired": expired,
            "remaining": remaining,
            "first_shortage": first_shortage,
            "incomplete": incomplete,
            "coverage": coverage,
        })

    results.sort(
        key=lambda row: (
            row["rank"],
            (
                row["first_shortage"]
                if isinstance(
                    row["first_shortage"], date
                )
                else date.max
            ) if row["rank"] == 0 else date.max,
            -row["shortage"]
                if row["rank"] == 0
                else -row["expired"],
            row["compound"].casefold(),
            row["unit"],
        )
    )

    return results


def summary(rows):
    return {
        "shortages": sum(
            row["shortage"] > 1e-9 for row in rows
        ),
        "expirations": sum(
            row["expired"] > 1e-9 for row in rows
        ),
        "reviews": sum(
            row["incomplete"]
            or row["unknown_stock"] > 1e-9
            for row in rows
        ),
        "first_shortage": min(
            (
                row["first_shortage"]
                for row in rows
                if row["shortage"] > 1e-9
                and row["first_shortage"] is not None
            ),
            default=None,
        ),
    }


@router.get("/planning-priorities")
def planning_priorities(
    request: Request,
    horizon: int = Query(28),
    compound: str = Query("", max_length=120),
    category: str = Query("all"),
    db: Session = Depends(get_db),
):
    if horizon not in HORIZONS:
        horizon = 28

    if category not in (
        "all", "shortage", "expiration", "review"
    ):
        category = "all"

    source, warnings = build_fefo(db)

    # Summary uses the unfiltered set, so filtering
    # does not silently change dashboard-wide counts.
    all_rows = priority_rows(source, horizon)

    rows = priority_rows(
        source,
        horizon,
        compound,
        category,
    )

    return render(
        request,
        "planning_priorities.html",
        rows=rows,
        totals=summary(all_rows),
        warnings=warnings,
        horizon=horizon,
        horizons=HORIZONS,
        compound=compound,
        category=category,
    )


@router.get("/planning-priorities.csv")
def planning_priorities_csv(
    horizon: int = Query(28),
    compound: str = Query("", max_length=120),
    category: str = Query("all"),
    db: Session = Depends(get_db),
):
    if horizon not in HORIZONS:
        horizon = 28

    if category not in (
        "all", "shortage", "expiration", "review"
    ):
        category = "all"

    source, warnings = build_fefo(db)

    rows = priority_rows(
        source,
        horizon,
        compound,
        category,
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Compound",
        "Unit",
        "Horizon days",
        "Priority",
        "Dated stock",
        "Unknown-date stock",
        "Scheduled demand",
        "Allocated",
        "Projected shortage",
        "First shortage",
        "Projected expiration loss",
        "Remaining dated stock",
        "Demand-rate coverage days",
        "Incomplete schedule",
    ])

    for row in rows:
        name = row["compound"]

        # Prevent spreadsheet formula interpretation.
        if name.lstrip().startswith(
            ("=", "+", "-", "@")
        ):
            name = "'" + name

        writer.writerow([
            name,
            row["unit"],
            horizon,
            row["status"],
            round(row["dated_stock"], 4),
            round(row["unknown_stock"], 4),
            round(row["demand"], 4),
            round(row["allocated"], 4),
            round(row["shortage"], 4),
            row["first_shortage"] or "",
            round(row["expired"], 4),
            round(row["remaining"], 4),
            (
                round(row["coverage"], 2)
                if row["coverage"] is not None
                else ""
            ),
            row["incomplete"],
        ])

    return Response(
        "\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
            'attachment; filename="planning-priorities.csv"'
        },
    )
