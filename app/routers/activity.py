
"""Unified, read-only Tracker activity timeline."""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    DoseLog,
    VitalReading,
    Purchase,
    Page,
    ProtocolRevision,
    Vial,
    Compound,
)
from ..templating import render

router = APIRouter()


def collect_activity(db, start, end, category="all"):
    events = []

    def add(when, kind, title, detail, href):
        if when is None:
            return

        if isinstance(when, date) and not isinstance(when, datetime):
            when = datetime.combine(
                when,
                datetime.min.time(),
            )

        if start <= when.date() <= end:
            if category in ("all", kind):
                events.append({
                    "when": when,
                    "kind": kind,
                    "title": title,
                    "detail": detail,
                    "href": href,
                })

    if category in ("all", "dose"):
        for log in db.scalars(select(DoseLog)):
            vial = db.get(Vial, log.vial_id)

            compound = (
                db.get(Compound, vial.compound_id)
                if vial else None
            )

            name = compound.name if compound else "Unknown compound"

            add(
                log.taken_at,
                "dose",
                name,
                f"{log.kind}: {log.entered_value:g} "
                f"{log.entered_unit}",
                "/doses",
            )

    if category in ("all", "vitals"):
        for reading in db.scalars(select(VitalReading)):
            parts = []

            if reading.weight_kg is not None:
                parts.append(
                    f"Weight {reading.weight_kg * 2.2046226218:.1f} lb"
                )

            if reading.systolic is not None:
                parts.append(
                    f"BP {reading.systolic}/"
                    f"{reading.diastolic or '—'}"
                )

            if reading.pulse_bpm is not None:
                parts.append(
                    f"Pulse {reading.pulse_bpm} bpm"
                )

            add(
                reading.measured_at,
                "vitals",
                "Vital reading",
                " · ".join(parts),
                "/vitals",
            )

    if category in ("all", "purchase"):
        for purchase in db.scalars(select(Purchase)):
            add(
                purchase.purchased_on,
                "purchase",
                "Purchase",
                purchase.vendor or "Unknown vendor",
                f"/purchases/{purchase.id}",
            )

    if category in ("all", "notes"):
        for page in db.scalars(select(Page)):
            add(
                page.created_at,
                "notes",
                "Note created",
                page.title,
                f"/pages/{page.id}",
            )

            if (
                page.updated_at
                and page.created_at
                and page.updated_at > page.created_at
            ):
                add(
                    page.updated_at,
                    "notes",
                    "Note updated",
                    page.title,
                    f"/pages/{page.id}",
                )

    if category in ("all", "protocol"):
        for revision in db.scalars(
            select(ProtocolRevision)
        ):
            add(
                revision.created_at,
                "protocol",
                "Protocol revision",
                f"Protocol #{revision.protocol_id}, "
                f"revision {revision.revision}",
                f"/protocols/{revision.protocol_id}/history",
            )

    events.sort(
        key=lambda item: item["when"],
        reverse=True,
    )

    return events


@router.get("/activity")
def activity(
    request: Request,
    start: str = "",
    end: str = "",
    category: str = "all",
    db: Session = Depends(get_db),
):
    today = date.today()

    try:
        start_date = (
            date.fromisoformat(start)
            if start else today - timedelta(days=30)
        )

        end_date = (
            date.fromisoformat(end)
            if end else today
        )
    except ValueError:
        raise HTTPException(
            400,
            "Invalid date",
        )

    if start_date > end_date:
        raise HTTPException(
            400,
            "Start date must precede end date",
        )

    if (end_date - start_date).days > 366:
        raise HTTPException(
            400,
            "Maximum date range is 366 days",
        )

    categories = {
        "all",
        "dose",
        "vitals",
        "purchase",
        "notes",
        "protocol",
    }

    if category not in categories:
        raise HTTPException(
            400,
            "Invalid category",
        )

    events = collect_activity(
        db,
        start_date,
        end_date,
        category,
    )

    return render(
        request,
        "activity.html",
        events=events,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        category=category,
        total=len(events),
    )
