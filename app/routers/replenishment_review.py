"""Read-only replenishment worklist using existing Tracker projections."""

import csv
import io
from collections import Counter
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..forecasting import forecast_inventory
from ..models import Compound
from ..templating import render
from .fefo_forecast import HORIZONS, build_fefo
from .planning_priorities import priority_rows

router = APIRouter()

HISTORY_WINDOWS = (30, 90, 180)
STATUSES = (
    "attention", "all", "shortfall", "depleted",
    "near-term", "review", "no-history", "stable",
)


def history_key(row):
    unit = row["unit"]
    return (
        row["name"].casefold(),
        "IU" if unit == "IU" else
        "mg" if unit == "mcg" else unit,
    )


def build_worklist(
    fefo_rows, compound_history, supply_history,
    compound_ids, horizon=28,
):
    """Combine read-only forecasts without recalculating inventory."""

    if horizon not in HORIZONS:
        raise ValueError("Unsupported horizon")

    histories = {
        history_key(row): row
        for row in compound_history
    }

    rows = []
    seen = set()

    for item in priority_rows(fefo_rows, horizon=horizon):
        key = (
            item["compound"].casefold(),
            item["unit"],
        )
        seen.add(key)

        history = histories.get(key)
        left = history["days_left"] if history else None
        usable = item["dated_stock"] + item["unknown_stock"]

        if usable <= 1e-9 and item["demand"] > 1e-9:
            status = "depleted"
        elif item["shortage"] > 1e-9:
            status = "shortfall"
        elif item["needs_review"]:
            status = "review"
        elif left is not None and left <= horizon:
            status = "near-term"
        elif left is None:
            status = "no-history"
        else:
            status = "stable"

        rows.append({
            "kind": "Compound",
            "name": item["compound"],
            "unit": item["unit"],
            "id": compound_ids.get(item["compound"].casefold()),
            "status": status,
            "remaining": usable,
            "scheduled": item["demand"],
            "shortage": item["shortage"],
            "first_shortage": item["first_shortage"],
            "incomplete": item["incomplete"],
            "undated": item["unknown_stock"] > 1e-9,
            "days_left": left,
            "depletion": history["depletion"] if history else None,
        })

    # Include inventory without an existing FEFO demand group.
    for hist in compound_history:
        key = history_key(hist)
        if key in seen:
            continue

        remaining = (
            hist["remaining"] / 1000
            if hist["unit"] == "mcg"
            else hist["remaining"]
        )
        left = hist["days_left"]

        if remaining <= 1e-9:
            status = "depleted"
        elif left is not None and left <= horizon:
            status = "near-term"
        elif left is None:
            status = "no-history"
        else:
            status = "stable"

        rows.append({
            "kind": "Compound",
            "name": hist["name"],
            "unit": key[1],
            "id": compound_ids.get(hist["name"].casefold()),
            "status": status,
            "remaining": remaining,
            "scheduled": None,
            "shortage": None,
            "first_shortage": None,
            "incomplete": False,
            "undated": False,
            "days_left": left,
            "depletion": hist["depletion"],
        })

    for hist in supply_history:
        remaining = hist["remaining"]
        left = hist["days_left"]

        if remaining <= 1e-9:
            status = "depleted"
        elif left is not None and left <= horizon:
            status = "near-term"
        elif left is None:
            status = "no-history"
        else:
            status = "stable"

        rows.append({
            "kind": "Supply",
            "name": hist["name"],
            "unit": "recorded units",
            "id": hist["id"],
            "status": status,
            "remaining": remaining,
            "scheduled": None,
            "shortage": None,
            "first_shortage": None,
            "incomplete": False,
            "undated": False,
            "days_left": left,
            "depletion": hist["depletion"],
        })

    order = {
        "shortfall": 0,
        "depleted": 1,
        "near-term": 2,
        "review": 3,
        "no-history": 4,
        "stable": 5,
    }

    rows.sort(key=lambda row: (
        order[row["status"]],
        row["first_shortage"] or date.max,
        row["name"].casefold(),
        row["kind"],
        row["id"] or 0,
    ))

    return rows


def fetch_worklist(db, horizon, history):
    source, warnings = build_fefo(db)
    compounds, supplies = forecast_inventory(
        db, window_days=history
    )
    ids = {
        c.name.casefold(): c.id
        for c in db.scalars(select(Compound))
    }

    rows = build_worklist(
        source, compounds, supplies, ids,
        horizon=horizon,
    )
    return rows, warnings


def parameters(horizon, history, category):
    return (
        horizon if horizon in HORIZONS else 28,
        history if history in HISTORY_WINDOWS else 90,
        category if category in STATUSES else "attention",
    )


def visible(rows, category, query):
    needle = query.strip().casefold()
    return [
        row for row in rows
        if (
            category == "all"
            or (category == "attention" and row["status"] != "stable")
            or row["status"] == category
        )
        and (not needle or needle in row["name"].casefold())
    ]


@router.get("/replenishment-review")
def replenishment_review(
    request: Request,
    horizon: int = Query(28),
    history: int = Query(90),
    category: str = Query("attention"),
    q: str = Query("", max_length=120),
    db: Session = Depends(get_db),
):
    horizon, history, category = parameters(
        horizon, history, category
    )
    rows, warnings = fetch_worklist(db, horizon, history)

    return render(
        request,
        "replenishment_review.html",
        rows=visible(rows, category, q),
        totals=Counter(r["status"] for r in rows),
        warnings=warnings,
        horizon=horizon,
        horizons=HORIZONS,
        history=history,
        windows=HISTORY_WINDOWS,
        category=category,
        q=q,
    )


@router.get("/replenishment-review.csv")
def replenishment_csv(
    horizon: int = Query(28),
    history: int = Query(90),
    category: str = Query("attention"),
    q: str = Query("", max_length=120),
    db: Session = Depends(get_db),
):
    horizon, history, category = parameters(
        horizon, history, category
    )
    rows, _ = fetch_worklist(db, horizon, history)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Type", "Item", "Unit", "Flag",
        "Usable or recorded stock", "Scheduled demand",
        "Scheduled shortfall", "First scheduled shortfall",
        "Historical days left", "Historical depletion",
        "Incomplete schedule", "Undated stock",
    ])

    for item in visible(rows, category, q):
        name = item["name"]

        # Protect spreadsheet programs against formula injection.
        if name.lstrip().startswith(("=", "+", "-", "@")):
            name = "'" + name

        writer.writerow([
            item["kind"],
            name,
            item["unit"],
            item["status"],
            round(item["remaining"], 4),
            "" if item["scheduled"] is None
               else round(item["scheduled"], 4),
            "" if item["shortage"] is None
               else round(item["shortage"], 4),
            item["first_shortage"] or "",
            "" if item["days_left"] is None
               else round(item["days_left"], 2),
            item["depletion"] or "",
            item["incomplete"],
            item["undated"],
        ])

    return Response(
        "\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
            'attachment; filename="replenishment-review.csv"'
        },
    )
