"""Per-protocol dashboard inventory forecast with shared current usage.

All active protocols remain visible even without stock or a usable schedule.
Depletion estimates consider current stages, not future changes or purchases.
"""
from collections import defaultdict
from datetime import date, timedelta
from math import isfinite

from .units import UnitError, parse_unit

UNITS = {"mass": "mcg", "iu": "IU", "volume": "mL"}


def weekly_base752(item):
    try:
        unit = parse_unit(item.amount_unit)
    except (UnitError, ValueError, TypeError):
        return None, None
    try:
        amount, frequency = float(item.amount_value), float(item.freq_count)
        if not (isfinite(amount) and amount > 0 and
                isfinite(frequency) and frequency > 0):
            return unit.dim, None
        if item.freq_period == "interval":
            per_week = amount * 7 / frequency
        elif item.freq_period in ("day", "week", "month"):
            days = {"day": 1, "week": 7,
                    "month": 365.2425 / 12}[item.freq_period]
            per_week = amount * frequency * 7 / days
        else:
            return unit.dim, None
        rate = per_week * unit.factor
        return unit.dim, rate if isfinite(rate) and rate > 0 else None
    except (OverflowError, ValueError, TypeError, ZeroDivisionError):
        return unit.dim, None


def stage752(protocol, item, today: date):
    if protocol.start_date is None:
        return "Set start date"
    if protocol.end_date is not None and protocol.end_date < today:
        return "Protocol ended"
    if today < protocol.start_date:
        return "Not started"
    day = (today - protocol.start_date).days
    if day < 7 * (item.start_week - 1):
        return "Upcoming stage"
    if item.end_week is not None and day >= 7 * item.end_week:
        return "Stage completed"
    return "Active"


def build_dashboard_forecasts752(protocols, inventory_dims, today: date):
    """Return (per-protocol rows, unique low-stock rows, unique watch rows)."""
    rows = []
    combined = defaultdict(float)
    for protocol in protocols:
        if not protocol.is_active:
            continue
        if not protocol.items:
            rows.append(dict(
                protocol=protocol.name, protocol_id=protocol.id,
                compound="—", compound_id=None, dimension=None,
                remaining=None, unit="", days_left=None, depletion=None,
                status="No compounds", low=False,
            ))
        for item in protocol.items:
            dim, weekly = weekly_base752(item)
            by_dimension = inventory_dims.get(item.compound_id, {})
            volume_quality = (by_dimension.get("_volume_quality")
                              if dim == "volume" else None)
            if (dim == "volume" and not volume_quality and
                    "volume" not in by_dimension and
                    any(name in by_dimension for name in ("mass", "iu"))):
                volume_quality = "missing"
            stock = (None if dim is None or volume_quality else
                     max(0.0, float(by_dimension.get(dim, 0.0))))
            status = stage752(protocol, item, today)
            if dim is None:
                status = "Invalid unit"
            elif weekly is None:
                status = "Invalid schedule"
            if status == "Active" and volume_quality:
                status = {
                    "missing": "Concentration unavailable",
                    "partial": "Volume data incomplete",
                    "mixed": "Mixed concentrations - review",
                }.get(volume_quality, "Concentration unavailable")
            if status == "Active":
                combined[(item.compound_id, dim)] += weekly
            rows.append(dict(
                protocol=protocol.name, protocol_id=protocol.id,
                compound=item.compound.name, compound_id=item.compound_id,
                dimension=dim, remaining=stock,
                unit=UNITS.get(dim, item.amount_unit),
                days_left=None, depletion=None, status=status, low=False,
            ))

    for row in rows:
        if row["status"] != "Active":
            continue
        rate = combined[(row["compound_id"], row["dimension"])]
        if not isfinite(rate) or rate <= 0:
            row["status"] = "Invalid schedule"
            continue
        days = 7 * row["remaining"] / rate
        row["days_left"] = days
        row["depletion"] = today + timedelta(days=min(days, 365000))
        row["low"] = days < 21
        row["status"] = ("No stock" if row["remaining"] == 0 else
                         "Low stock" if row["low"] else "On hand")

    rows.sort(key=lambda row: (
        row["days_left"] is None,
        row["days_left"] if row["days_left"] is not None else float("inf"),
        row["protocol"].casefold(), row["compound"].casefold(),
    ))
    watch = {}
    for row in rows:
        if row["days_left"] is not None:
            watch.setdefault((row["compound_id"], row["dimension"]), row)
    unique = list(watch.values())
    return rows, [row for row in unique if row["low"]], unique
