from datetime import datetime, timedelta, time
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import VitalReading, DoseLog, LabReport, Protocol
from ..templating import render
from .. import config, metrics

router = APIRouter()
RANGES = {30: "30 days", 90: "90 days", 365: "1 year", 3650: "All"}

@router.get("/health-timeline")
def timeline(request: Request, days: int = 90, db: Session = Depends(get_db)):
    days = days if days in RANGES else 90
    since = datetime.now() - timedelta(days=days)
    events = []
    for r in db.scalars(select(VitalReading).where(VitalReading.measured_at >= since)):
        parts = []
        if r.weight_kg is not None:
            parts.append(f"Weight {metrics.weight_from_kg(r.weight_kg, config.WEIGHT_UNIT):.1f} {config.WEIGHT_UNIT}")
        if r.systolic is not None:
            parts.append(f"BP {r.systolic}/{r.diastolic or '—'}")
        if r.pulse_bpm is not None:
            parts.append(f"Pulse {r.pulse_bpm} bpm")
        events.append(dict(at=r.measured_at, type="Vital", title=" · ".join(parts), detail=r.context or r.notes, link="/vitals"))
    for d in db.scalars(select(DoseLog).where(DoseLog.taken_at >= since)):
        events.append(dict(at=d.taken_at, type="Dose" if d.kind == "dose" else "Waste", title=f"{d.vial.compound.name}: {d.entered_value:g} {d.entered_unit}", detail=d.site or d.notes, link="/doses"))
    for report in db.scalars(select(LabReport).where(LabReport.drawn_on >= since.date())):
        events.append(dict(at=datetime.combine(report.drawn_on, time.min), type="Lab", title=f"{report.lab_name or 'Lab report'} · {len(report.results)} results", detail=report.notes, link="/labs"))
    for p in db.scalars(select(Protocol)):
        if p.start_date and p.start_date >= since.date():
            events.append(dict(at=datetime.combine(p.start_date, time.min), type="Protocol", title=f"{p.name} · start date", detail="Scheduled protocol start, not a confirmed administration", link="/protocols"))
        if p.end_date and p.end_date >= since.date():
            events.append(dict(at=datetime.combine(p.end_date, time.min), type="Protocol", title=f"{p.name} · end date", detail="Scheduled protocol end", link="/protocols"))
    events.sort(key=lambda x: x["at"], reverse=True)
    return render(request, "health_timeline.html", events=events, days=days, ranges=RANGES)
