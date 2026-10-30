
"""Read-only first-expiring-first-out inventory simulation."""

import csv
import io
from collections import defaultdict
from datetime import date, timedelta
from math import isfinite

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Compound, Protocol, Vial
from ..services import vial_views
from ..templating import render
from .. import calendar as cal
from ..projection_exclusions import exclusions_for, excluded
from .inventory_forecast import normalized

router = APIRouter()

HORIZONS = (7, 14, 28, 56)


def finite_positive(value):
    try:
        number = float(value)
        return number if isfinite(number) and number > 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def simulate_fefo(stock, events, today, horizon_days):
    """
    Pure-Python FEFO simulation.

    Stock:
        id, remaining, expiry

    Events:
        date, amount

    Inventory with unknown expiry is not included.

    An expiry date is treated conservatively: stock is
    removed before demand scheduled on that date.

    Does not change database records.
    """

    end = today + timedelta(days=horizon_days)

    vials = [
        {
            "id": row["id"],
            "remaining": float(row["remaining"]),
            "expiry": row["expiry"],
        }
        for row in stock
        if row["remaining"] > 0
        and row["expiry"] is not None
        and row["expiry"] >= today
    ]

    vials.sort(key=lambda x: (x["expiry"], x["id"]))

    scheduled = sorted(
        [
            (when, float(amount))
            for when, amount in events
            if today <= when < end
        ],
        key=lambda x: x[0],
    )

    consumed = 0.0
    shortage = 0.0
    expired = 0.0
    first_shortage = None

    def expire_through(day):
        nonlocal expired

        for vial in vials:
            if vial["expiry"] <= day and vial["remaining"] > 0:
                expired += vial["remaining"]
                vial["remaining"] = 0.0

    for when, amount in scheduled:
        expire_through(when)

        needed = amount

        for vial in vials:
            if needed <= 0:
                break

            if vial["remaining"] <= 0:
                continue

            taken = min(vial["remaining"], needed)

            vial["remaining"] -= taken
            needed -= taken
            consumed += taken

        if needed > 1e-9:
            shortage += needed
            if first_shortage is None:
                first_shortage = when

    # Remove inventory expiring before the end of the horizon.
    # The horizon's final day is not itself simulated.
    expire_through(end - timedelta(days=1))

    remaining = sum(v["remaining"] for v in vials)

    return {
        "demand": sum(amount for _, amount in scheduled),
        "consumed": consumed,
        "shortage": shortage,
        "expired": expired,
        "remaining": remaining,
        "first_shortage": first_shortage,
        "events": len(scheduled),
    }


def build_fefo(db, today=None):
    today = today or date.today()

    end = today + timedelta(days=max(HORIZONS))

    compounds = {
        c.id: c.name
        for c in db.scalars(select(Compound)).all()
    }

    vials = list(db.scalars(select(Vial)).all())

    views = vial_views(db, vials)

    # TRACKER_RELEASE_217_224
    stock = defaultdict(list)
    unknown = defaultdict(float)
    warnings = []

    expired_existing = defaultdict(float)
    undated_vials = defaultdict(int)
    expired_vials = defaultdict(int)

    for vial in vials:
        if vial.status not in ("sealed", "in_use"):
            continue

        if vial.closed_on is not None:
            continue

        view = views[vial.id]

        remaining = finite_positive(view.remaining_base)

        if remaining is None:
            continue

        # vial_views() reports base mass in mcg and IU
        # in its own independent dimension.
        unit = "IU" if view.dim == "iu" else "mg"
        scale = 1 if unit == "IU" else 1000

        key = (vial.compound_id, unit)

        expiry = min(
            (
                d for d in (
                    vial.expires_on,
                    vial.beyond_use_on,
                )
                if d is not None
            ),
            default=None,
        )

        if expiry is None:
            unknown[key] += remaining / scale
            undated_vials[key] += 1
            continue

        if expiry < today:
            # Existing expired inventory is not future
            # projected expiration loss.
            expired_existing[key] += remaining / scale
            expired_vials[key] += 1
            continue

        stock[key].append({
            "id": vial.id,
            "remaining": remaining / scale,
            "expiry": expiry,
        })

    protocols = list(
        db.scalars(
            select(Protocol).where(
                Protocol.is_active.is_(True)
            )
        )
    )

    item_ids = [
        item.id
        for protocol in protocols
        for item in protocol.items
    ]

    exclusions = exclusions_for(db, item_ids)

    events = defaultdict(list)
    invalid = set()
    active_keys = set()

    for protocol in protocols:
        if protocol.start_date is None:
            warnings.append(
                f"{protocol.name}: missing start date; "
                "forecast incomplete"
            )

            # Preserve affected compounds in the forecast
            # even when no occurrences can be calculated.
            for item in protocol.items:
                unit = (
                    "IU"
                    if item.amount_unit == "IU"
                    else "mg"
                )
                key = (item.compound_id, unit)
                active_keys.add(key)
                invalid.add(key)

            continue

        if (
            protocol.end_date is not None
            and protocol.end_date < today
        ):
            continue

        if protocol.start_date >= end:
            continue

        for item in protocol.items:
            unit = (
                "IU"
                if item.amount_unit == "IU"
                else "mg"
            )

            key = (item.compound_id, unit)
            active_keys.add(key)

            base = normalized(
                item.amount_value,
                item.amount_unit,
            )

            if (
                base is None
                or not isfinite(base)
                or base <= 0
            ):
                invalid.add(key)
                warnings.append(
                    f"{protocol.name}: invalid amount for "
                    f"{compounds.get(item.compound_id, item.compound_id)}"
                )
                continue

            scale = 1 if unit == "IU" else 1000
            amount = base / scale

            try:
                occurrences = cal.staged_occurrences(
                    item,
                    protocol.start_date,
                    (end - protocol.start_date).days + 1,
                )

                for when in occurrences:
                    if when < today or when >= end:
                        continue

                    if (
                        protocol.end_date is not None
                        and when > protocol.end_date
                    ):
                        continue

                    if excluded(exclusions, item.id, when):
                        continue

                    events[key].append((when, amount))

            except (ValueError, TypeError, OverflowError) as exc:
                invalid.add(key)
                warnings.append(
                    f"{protocol.name}: schedule unavailable "
                    f"({type(exc).__name__})"
                )

    rows = []

    keys = sorted(
        set(stock)
        | set(unknown)
        | set(expired_existing)
        | active_keys,
        key=lambda key: (
            compounds.get(key[0], "").casefold(),
            key[1],
        ),
    )

    for key in keys:
        compound_id, unit = key

        inventory = stock.get(key, [])
        demand_events = events.get(key, [])

        horizons = {}

        for days in HORIZONS:
            horizons[days] = simulate_fefo(
                inventory,
                demand_events,
                today,
                days,
            )

        rows.append({
            "compound": compounds.get(
                compound_id,
                f"Compound #{compound_id}",
            ),
            "unit": unit,
            "vials": len(inventory),
            "dated_stock": sum(
                v["remaining"] for v in inventory
            ),
            "unknown_stock": unknown.get(key, 0.0),
            "expired_existing": expired_existing.get(
                key, 0.0
            ),
            "undated_vials": undated_vials.get(key, 0),
            "expired_vials": expired_vials.get(key, 0),
            "incomplete": key in invalid,
            "horizons": horizons,
        })

    for key in keys:
        compound_id, unit = key
        name = compounds.get(
            compound_id,
            f"Compound #{compound_id}",
        )

        if undated_vials.get(key, 0):
            warnings.append(
                f"{name} ({unit}): "
                f"{undated_vials[key]} vial(s) without "
                "expiration or beyond-use date; "
                "excluded from FEFO allocation"
            )

        if expired_vials.get(key, 0):
            warnings.append(
                f"{name} ({unit}): "
                f"{expired_vials[key]} already-expired "
                "vial(s) excluded from FEFO allocation"
            )

    return rows, warnings

@router.get("/fefo-forecast")
def fefo_forecast(
    request: Request,
    db: Session = Depends(get_db),
):
    rows, warnings = build_fefo(db)

    return render(
        request,
        "fefo_forecast.html",
        rows=rows,
        warnings=warnings,
        horizons=HORIZONS,
    )


@router.get("/fefo-forecast.csv")
def fefo_forecast_csv(
    db: Session = Depends(get_db),
):
    rows, warnings = build_fefo(db)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Compound",
        "Unit",
        "Dated stock",
        "Unknown-date stock",
        "Horizon days",
        "Scheduled events",
        "Demand",
        "Allocated",
        "Shortage",
        "Expired unused",
        "Remaining dated stock",
        "First shortage",
        "Incomplete schedule",
    ])

    for row in rows:
        name = row["compound"]

        if name.lstrip().startswith(
            ("=", "+", "-", "@")
        ):
            name = "'" + name

        for days in HORIZONS:
            result = row["horizons"][days]

            writer.writerow([
                name,
                row["unit"],
                round(row["dated_stock"], 4),
                round(row["unknown_stock"], 4),
                days,
                result["events"],
                round(result["demand"], 4),
                round(result["consumed"], 4),
                round(result["shortage"], 4),
                round(result["expired"], 4),
                round(result["remaining"], 4),
                result["first_shortage"] or "",
                row["incomplete"],
            ])

    return Response(
        "\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
            'attachment; filename="fefo-forecast.csv"'
        },
    )
