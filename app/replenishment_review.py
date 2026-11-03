"""Read-only replenishment worklist from Tracker's existing usage forecasts.

This module does not calculate purchases or recommend acquisition quantities.
It preserves forecast units and distinguishes absent usage evidence from
estimated near-term stock depletion.
"""
from __future__ import annotations

from math import isfinite

from sqlalchemy import select

from .forecasting import forecast_inventory
from .models import Compound, Supply, SupplyCategory
from .supply_categories import DEFAULTS

WINDOWS = (30, 90, 180)
HORIZONS = (7, 14, 21, 30, 60, 90)


def _finite(value):
    try:
        number = float(value)
        return number if isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def classify_forecast(kind: str, forecast: dict, horizon: int,
                      compound_ids: dict[str, int],
                      supply_unit: str = "") -> dict | None:
    """Return a replenishment watch row, or None if coverage exceeds horizon."""
    remaining = _finite(forecast.get("remaining"))
    left = _finite(forecast.get("days_left"))
    used = _finite(forecast.get("used"))
    if remaining is None or remaining < 0:
        return None  # malformed stock should not be presented as usable stock

    if remaining <= 0:
        state, label = "depleted", "No recorded stock remaining"
    elif left is not None and left <= horizon:
        state, label = "soon", "Estimated depletion within horizon"
    elif left is None:
        state, label = "unestimated", "Insufficient recorded usage to estimate"
    else:
        return None

    name = str(forecast.get("name") or "Unnamed item")
    if kind == "Compound":
        cid = compound_ids.get(name)
        review = f"/vials?status=active&compound_id={cid}" if cid else "/vials"
        unit = str(forecast.get("unit") or "")
    else:
        review = "/supplies#supply-stock"
        unit = supply_unit
    return {
        "category": kind,
        "name": name,
        "unit": unit,
        "remaining": remaining,
        "used": used,
        "days_left": left,
        "depletion": forecast.get("depletion"),
        "state": state,
        "label": label,
        "review_href": review,
        "purchase_href": "/purchases#new-purchase",
    }


def build_replenishment(db, history_days: int = 90,
                        horizon_days: int = 21) -> dict:
    if history_days not in WINDOWS:
        raise ValueError("History window must be 30, 90 or 180 days")
    if horizon_days not in HORIZONS:
        raise ValueError("Invalid replenishment horizon")
    compounds, supplies = forecast_inventory(db, window_days=history_days)
    compound_ids = {
        c.name: c.id for c in db.scalars(select(Compound)).all()
    }
    # Read supply category units without seeding or modifying categories.
    category_units = {key: unit for key, _label, unit in DEFAULTS}
    category_units.update({
        category.key: category.unit
        for category in db.scalars(select(SupplyCategory)).all()
    })
    supply_units = {
        supply.id: category_units.get(supply.kind, "")
        for supply in db.scalars(select(Supply)).all()
    }
    urgent, unknown = [], []
    for category, rows in (("Compound", compounds), ("Supply", supplies)):
        for forecast in rows:
            item = classify_forecast(
                category, forecast, horizon_days, compound_ids,
                supply_unit=supply_units.get(forecast.get("id"), "")
                if category == "Supply" else "",
            )
            if item is None:
                continue
            (unknown if item["state"] == "unestimated" else urgent).append(item)
    urgent.sort(key=lambda x: (
        0 if x["state"] == "depleted" else 1,
        x["days_left"] if x["days_left"] is not None else float("inf"),
        x["category"], x["name"].casefold(),
    ))
    unknown.sort(key=lambda x: (x["category"], x["name"].casefold()))
    return {
        "urgent": urgent,
        "unknown": unknown,
        "history_days": history_days,
        "horizon_days": horizon_days,
        "total": len(urgent) + len(unknown),
    }


def safe_csv_text(value) -> str:
    """Prevent spreadsheet formula execution in user-controlled text cells."""
    s = str(value if value is not None else "")
    if s.startswith(("\t", "\r", "\n")) or s.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + s
    return s
