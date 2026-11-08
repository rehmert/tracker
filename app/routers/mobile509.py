"""Release 509: phone-first daily home and environment-specific PWA identity.

The daily view reads only from the user's existing scoped database.
There are no mobile-specific tables, caches or background writes.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, metrics, services
from ..models import DoseLog, Protocol, VitalReading, Vial
from ..mobile_shortcuts511 import recent_preparations
from ..projection_exclusions import exclusions_for
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..today import schedule_summary

router = APIRouter()


@router.get("/mobile", include_in_schema=False)
def mobile_today(request: Request, db: Session = Depends(get_scoped_db390)):
    """Small, useful and non-mutating snapshot of actuals and planned items."""
    now = datetime.now()
    today = now.date()
    start = datetime.combine(today - timedelta(days=7), datetime.min.time())
    end = datetime.combine(today + timedelta(days=1), datetime.min.time())

    protocols = list(db.scalars(select(Protocol).order_by(Protocol.name)))
    recent_week = list(db.scalars(
        select(DoseLog).where(
            DoseLog.kind == "dose",
            DoseLog.taken_at >= start,
            DoseLog.taken_at < end,
        ).order_by(DoseLog.taken_at.desc(), DoseLog.id.desc())
    ))
    item_ids = [item.id for protocol in protocols for item in protocol.items]
    summary = schedule_summary(
        protocols, recent_week, today,
        exclusions=exclusions_for(db, item_ids),
    )

    recent_doses = list(db.scalars(
        select(DoseLog)
        .where(DoseLog.kind == "dose")
        .order_by(DoseLog.taken_at.desc(), DoseLog.id.desc())
        .limit(5)
    ))
    active_vials = list(db.scalars(
        select(Vial).where(Vial.status.in_(("in_use", "sealed")))
    ))
    recent_shortcuts = recent_preparations(
        db, active_vials, services.vial_views(db, active_vials)
    ) if active_vials else []
    recent_vital_rows = list(db.scalars(
        select(VitalReading)
        .order_by(VitalReading.measured_at.desc(), VitalReading.id.desc())
        .limit(5)
    ))
    recent_vitals = [
        (
            reading,
            metrics.weight_from_kg(reading.weight_kg, config.WEIGHT_UNIT)
            if reading.weight_kg is not None else None,
        )
        for reading in recent_vital_rows
    ]

    # The latest available reading for each measurement is independent.
    def latest(column):
        return db.scalar(
            select(VitalReading).where(column.is_not(None))
            .order_by(VitalReading.measured_at.desc(), VitalReading.id.desc())
            .limit(1)
        )

    weight_row = latest(VitalReading.weight_kg)
    bp_row = latest(VitalReading.systolic)
    pulse_row = latest(VitalReading.pulse_bpm)

    return render(
        request, "mobile_today509.html",
        now=now.strftime("%Y-%m-%dT%H:%M"),
        today=today,
        instance=config.instance_label(),
        unit=config.WEIGHT_UNIT,
        summary=summary,
        recent_doses=recent_doses, recent_shortcuts=recent_shortcuts,
        recent_vitals=recent_vitals,
        last_weight=(
            metrics.weight_from_kg(weight_row.weight_kg, config.WEIGHT_UNIT)
            if weight_row else None
        ),
        last_weight_when=weight_row.measured_at if weight_row else None,
        last_bp=bp_row,
        last_pulse=pulse_row.pulse_bpm if pulse_row else None,
        last_pulse_when=pulse_row.measured_at if pulse_row else None,
    )
