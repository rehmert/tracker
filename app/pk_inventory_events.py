"""Approximate read-only FEFO allocation for PK experiments.

Forecasted allocation is pooled across vials and does not
prove physical vial suitability or sterility.
"""
from datetime import date, timedelta
from math import isfinite

from sqlalchemy import select

from . import services
from .models import Protocol, Vial
from .pk_schedule_core import schedule_doses


def allocate_events(vials, events, start, end):
    """Pure function: date-eligible inventory consumed FEFO.

    Vials: mapping with remaining_mg, expires_on,
    beyond_use_on, status, closed_on.
    Events: (datetime, mg). No database operations.
    """
    stock=[]
    expiring=0.0

    for vial in vials:
        if vial.get("status") not in ("sealed","in_use"):
            continue
        if vial.get("closed_on"):
            continue
        remaining=float(vial.get("remaining_mg",0))
        if not isfinite(remaining) or remaining<=0:
            continue

        dates=[
            d for d in (
                vial.get("expires_on"),
                vial.get("beyond_use_on"),
            ) if d is not None
        ]
        expiry=min(dates) if dates else None
        if expiry is not None and expiry<start:
            continue
        if expiry is not None and start<=expiry<end:
            expiring+=remaining
        stock.append({
            "id": vial.get("id"),
            "remaining": remaining,
            "initial": remaining,
            "expiry": expiry,
        })

    stock.sort(key=lambda entry:
        entry["expiry"] or date.max
    )

    available=sum(x["remaining"] for x in stock)
    shortage=None
    total_demand=0.0
    ledger=[]
    processed=0
    allocated_total=0.0
    unfilled_total=0.0

    for at,raw_amount in sorted(events):
        amount=float(raw_amount)
        if not isfinite(amount) or amount<=0:
            raise ValueError("Invalid forecast administration")

        if not start<=at.date()<end:
            continue

        processed+=1
        total_demand+=amount
        required=amount
        allocation=[]
        remaining_before=sum(
            vial["remaining"] for vial in stock
            if vial["expiry"] is None or
            vial["expiry"]>=at.date()
        )
        for vial in stock:
            if vial["expiry"] is not None and \
                    vial["expiry"]<at.date():
                continue
            used=min(required,vial["remaining"])
            vial["remaining"]-=used
            required-=used
            if used > 0 and vial["id"] is not None:
                allocation.append({
                    "vial_id": vial["id"],
                    "allocated_mg": round(used,5),
                })
            if required<=1e-9:
                break

        allocated_total+=max(0.0,amount-required)
        unfilled_total+=max(0.0,required)
        if required>1e-9 and shortage is None:
            shortage=at.date().isoformat()

        if len(ledger)<1000:
            ledger.append({
                "at":at.isoformat(),
                "demand_mg":round(amount,5),
                "allocated_mg":round(
                    max(0.0,amount-required),5
                ),
                "unfilled_mg":round(
                    max(0.0,required),5
                ),
                "eligible_before_mg":round(
                    remaining_before,5
                ),
                "vial_allocations": allocation,
                "remaining_usable_mg":round(
                    sum(
                        vial["remaining"] for vial in stock
                        if vial["expiry"] is None or
                        vial["expiry"]>=at.date()
                    ),5
                ),
            })

    return {
        "starting_usable_mg":round(available,5),
        "demand_mg":round(total_demand,5),
        "remaining_after_allocation_mg":round(
            sum(x["remaining"] for x in stock),5
        ),
        "remaining_usable_at_horizon_mg":round(
            sum(
                x["remaining"] for x in stock
                if x["expiry"] is None or x["expiry"]>=end
            ),5
        ),
        "remaining_expired_at_horizon_mg":round(
            sum(
                x["remaining"] for x in stock
                if x["expiry"] is not None and x["expiry"]<end
            ),5
        ),
        "expiring_during_window_mg":round(expiring,5),
        "first_shortage_date":shortage,
        "allocation_method":"Approximate FEFO",
        "event_count":processed,
        "forecast_events":ledger,
        "total_unfilled_mg":round(unfilled_total,5),
        "total_allocated_mg":round(allocated_total,5),
        "demand_reconciled":abs(
            total_demand-allocated_total-unfilled_total
        )<=max(1e-7,total_demand*1e-9),
        "forecast_truncated":processed>len(ledger),
        "vial_balances":[
            {
                "id":v["id"],
                "initial_mg":round(v["initial"],5),
                "allocated_mg":round(
                    v["initial"]-v["remaining"],5
                ),
                "remaining_mg":round(v["remaining"],5),
                "expiry":(
                    v["expiry"].isoformat()
                    if v["expiry"] else None
                ),
            }
            for v in stock if v["id"] is not None
        ],
    }


def forecast_inventory(
    db, protocol_id, compound_id, days, modified
):
    """Pool selected experiment with other active protocols."""
    today=date.today()
    end=today+timedelta(days=days)

    vials=list(db.scalars(
        select(Vial).where(Vial.compound_id==compound_id)
    ))
    views=services.vial_views(db,vials)

    stock=[]
    for vial in vials:
        view=views.get(vial.id)
        if not view or view.dim!="mass":
            continue

        factor = {
            "mg":1, "mcg":0.001, "g":1000
        }.get(vial.content_unit)

        nominal = (
            float(vial.content_value) * factor / vial.volume_ml
            if (
                factor is not None
                and vial.volume_ml
                and vial.volume_ml > 0
            )
            else None
        )

        stock.append({
            "id":vial.id,
            "label":vial.label or f"Vial #{vial.id}",
            "nominal_mg_per_ml":(
                round(nominal,5)
                if nominal is not None else None
            ),
            "historical_cents_per_mg":
                view.cost_per_base*1000,
            "remaining_mg":view.remaining_base/1000,
            "expires_on":vial.expires_on,
            "beyond_use_on":vial.beyond_use_on,
            "closed_on":vial.closed_on,
            "status":vial.status,
        })

    selected_events=[
        (at,mg) for at,mg in modified
        if today<=at.date()<end
    ]

    other=[]
    skipped=0
    active=list(db.scalars(
        select(Protocol).where(
            Protocol.is_active.is_(True),
            Protocol.id!=protocol_id,
        )
    ))

    for protocol in active:
        if protocol.end_date and protocol.end_date<today:
            continue

        anchor=protocol.start_date or today
        span=(end-anchor).days

        if not 0<span<=730:
            skipped+=1
            continue

        try:
            doses=schedule_doses(
                protocol,compound_id,anchor,span
            )
        except (ValueError,OverflowError):
            skipped+=1
            continue

        other.extend(
            (at,mg) for at,mg in doses
            if today<=at.date()<end and (
                protocol.end_date is None or
                at.date()<=protocol.end_date
            )
        )

    rows=allocate_events(
        stock,selected_events+other,today,end
    )

    lookup = {v["id"]:v for v in stock}
    priced = [
        v for v in stock
        if (
            v["historical_cents_per_mg"] > 0
            and v["remaining_mg"] > 0
        )
    ]

    cost_per_mg = (
        sum(
            v["historical_cents_per_mg"] * v["remaining_mg"]
            for v in priced
        ) / sum(v["remaining_mg"] for v in priced)
        if priced else None
    )

    vial_estimates = [
        {
            **item,
            "label":lookup[item["id"]]["label"],
            "nominal_mg_per_ml":
                lookup[item["id"]]["nominal_mg_per_ml"],
        }
        for item in rows["vial_balances"]
        if item["id"] in lookup
    ]

    return {
        **rows,
        "vial_estimates":vial_estimates[:100],
        "unfilled_replenishment_mg":
            rows["total_unfilled_mg"],
        "estimated_replenishment_cost":(
            round(
                rows["total_unfilled_mg"]*cost_per_mg/100,
                2,
            )
            if cost_per_mg is not None else None
        ),
        "selected_future_demand_mg":round(
            sum(mg for _,mg in selected_events),5
        ),
        "other_active_demand_mg":round(
            sum(mg for _,mg in other),5
        ),
        "unmodeled_active_protocols":skipped,
        "forecast_caveat":(
            "Read-only approximate allocation of recorded "
            "remaining mass, including competing active "
            "protocols. Uses future expiry/BUD dates and "
            "first-expiring-first-out allocation. Does not "
            "model opening losses, vial preparation, stock "
            "replenishment, unrecorded consumption or "
            "physical vial suitability. No stock reserved."
        ),
    }
