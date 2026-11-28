"""Release 509: phone-first daily home and environment-specific PWA identity.

The daily view reads only from the user's existing scoped database.
There are no mobile-specific tables, caches or background writes.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, metrics
from ..models import DoseLog, Protocol, VitalReading
from ..scoped_db390 import get_scoped_db390
from ..templating import render
from ..daily_workspace790 import summary790, regimen790
from ..google_protocol_review783 import review_rows783
from ..daily_summary674 import snapshot674
from .wellness807 import today_context807
from ..today_priorities765 import missing_coa_count765, passed_date_examples765

router = APIRouter()


@router.get("/mobile", include_in_schema=False)
def mobile_today(request: Request, db: Session = Depends(get_scoped_db390),
                 wellness_day: str = "", wellness_symptom: int = 0):
    """Small, useful and non-mutating snapshot of actuals and planned items."""
    now = datetime.now()
    today = now.date()
    summary = summary790(db, today)

    recent_doses = list(db.scalars(
        select(DoseLog)
        .where(DoseLog.kind == "dose")
        .order_by(DoseLog.taken_at.desc(), DoseLog.id.desc())
        .limit(5)
    ))
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

    food_engine = None
    try:
        from ..food_engine392 import get_food_engine392
        food_engine = get_food_engine392(request)
    except PermissionError:
        # Secondary workspaces cannot access administrator-only food storage.
        pass
    except HTTPException as exc:
        if exc.status_code not in (403, 503):
            raise
    daily674 = snapshot674(db, today, food_engine)
    no_coa_count = missing_coa_count765(db)
    passed_date_vials = passed_date_examples765(db, today, limit=4)

    return render(
        request, "mobile_today509.html",
        now=now.strftime("%Y-%m-%dT%H:%M"),
        today=today,
        **today_context807(db, wellness_day, wellness_symptom),
        instance=config.instance_label(),
        unit=config.WEIGHT_UNIT,
        summary=summary,
        google_review_rows=review_rows783(db),
        regimen_origin='today', **regimen790(db, today),
        recent_doses=recent_doses,
        daily674=daily674,
        no_coa_count=no_coa_count,
        passed_date_vials=passed_date_vials,
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
