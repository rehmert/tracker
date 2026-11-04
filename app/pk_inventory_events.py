"""Approximate read-only FEFO allocation for PK experiments.

Forecasted allocation is pooled across vials and does not
prove physical vial suitability or sterility.
"""
from datetime import date, timedelta
from math import isfinite

from sqlalchemy import select

from . import services
from .models import Protocol, Vial
from .pk_precision import schedule_doses


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
            "remaining":remaining,
            "expiry":expiry,
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

        stock.append({
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

    return {
        **rows,
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
