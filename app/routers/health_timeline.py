"""Read-only timeline of recorded health events and active protocol milestones."""
import csv
import io
from collections import Counter
from datetime import datetime, timedelta, time
from itertools import groupby

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, metrics
from ..db import get_db
from ..models import VitalReading, DoseLog, LabReport, Protocol
from ..templating import render

router = APIRouter()
# The "All" option retains its existing value for bookmarked URLs but no
# longer imposes an arbitrary ten-year cutoff.
RANGES = {30: "30 days", 90: "90 days", 365: "1 year", 3650: "All"}
EVENT_TYPES = {
    "all": "All event types",
    "Vital": "Vitals",
    "Dose": "Doses",
    "Waste": "Waste",
    "Lab": "Lab reports",
    "Protocol": "Active protocols",
}


def _timeline_context(
    db: Session,
    days: int = 90,
    event_type: str = "all",
    q: str = "",
):
    """One read-only source for both on-screen entries and CSV exports."""
    days = days if days in RANGES else 90
    event_type = event_type if event_type in EVENT_TYPES else "all"
    q = q.strip()[:100]
    search = q.casefold()
    since = None if days == 3650 else datetime.now() - timedelta(days=days)

    events = []

    vital_query = select(VitalReading)
    if since is not None:
        vital_query = vital_query.where(VitalReading.measured_at >= since)
    for reading in db.scalars(vital_query):
        parts = []
        if reading.weight_kg is not None:
            parts.append(
                f"Weight {metrics.weight_from_kg(reading.weight_kg, config.WEIGHT_UNIT):.1f} {config.WEIGHT_UNIT}"
            )
        if reading.systolic is not None:
            parts.append(f"BP {reading.systolic}/{reading.diastolic or '—'}")
        if reading.pulse_bpm is not None:
            parts.append(f"Pulse {reading.pulse_bpm} bpm")
        detail = " · ".join(filter(None, (reading.context, reading.notes)))
        events.append(dict(
            at=reading.measured_at, type="Vital", title=" · ".join(parts),
            detail=detail, link=f"/vitals/{reading.id}/edit",
        ))

    dose_query = select(DoseLog)
    if since is not None:
        dose_query = dose_query.where(DoseLog.taken_at >= since)
    for dose in db.scalars(dose_query):
        events.append(dict(
            at=dose.taken_at, type="Dose" if dose.kind == "dose" else "Waste",
            title=f"{dose.vial.compound.name}: {dose.entered_value:g} {dose.entered_unit}",
            detail=" · ".join(filter(None, (dose.site, dose.notes))),
            link=f"/doses/{dose.id}/edit",
        ))

    report_query = select(LabReport)
    if since is not None:
        report_query = report_query.where(LabReport.drawn_on >= since.date())
    for report in db.scalars(report_query):
        events.append(dict(
            at=datetime.combine(report.drawn_on, time.min), type="Lab",
            title=f"{report.lab_name or 'Lab report'} · {len(report.results)} results",
            detail=report.notes, link=f"/labs/{report.id}",
        ))

    # What-if plans remain excluded regardless of search or filter settings.
    for protocol in db.scalars(
        select(Protocol).where(Protocol.is_active.is_(True))
    ):
        if protocol.start_date and (since is None or protocol.start_date >= since.date()):
            events.append(dict(
                at=datetime.combine(protocol.start_date, time.min),
                type="Protocol", title=f"{protocol.name} · start date",
                detail="Scheduled protocol start, not a confirmed administration",
                link=f"/protocols/{protocol.id}",
            ))
        if protocol.end_date and (since is None or protocol.end_date >= since.date()):
            events.append(dict(
                at=datetime.combine(protocol.end_date, time.min),
                type="Protocol", title=f"{protocol.name} · end date",
                detail="Scheduled protocol end", link=f"/protocols/{protocol.id}",
            ))

    # Counts describe the selected time range before applying type and text
    # filters, so users can see what is available without changing filters.
    counts = Counter(event["type"] for event in events)
    total = len(events)
    events = [
        event for event in events
        if (event_type == "all" or event["type"] == event_type)
        and (not search or search in " ".join(
            (event["title"], event["detail"] or "", event["type"])
        ).casefold())
    ]
    events.sort(key=lambda event: event["at"], reverse=True)
    groups = [
        {"day": day, "events": list(day_events)}
        for day, day_events in groupby(events, key=lambda event: event["at"].date())
    ]
    return dict(
        events=events, groups=groups,
        days=days, ranges=RANGES, event_type=event_type, event_types=EVENT_TYPES,
        q=q, total=total, counts=counts,
    )


@router.get("/health-timeline")
def timeline(
    request: Request,
    days: int = 90,
    event_type: str = "all",
    q: str = "",
    db: Session = Depends(get_db),
):
    return render(
        request, "health_timeline.html",
        **_timeline_context(db, days=days, event_type=event_type, q=q),
    )


def _csv_safe(value) -> str:
    """Prevent Excel and similar spreadsheet apps from evaluating user text."""
    text = "" if value is None else str(value)
    if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


@router.get("/health-timeline/export.csv")
def export_timeline_csv(
    days: int = 90,
    event_type: str = "all",
    q: str = "",
    db: Session = Depends(get_db),
):
    """Download exactly the entries shown by the selected timeline filters."""
    context = _timeline_context(db, days=days, event_type=event_type, q=q)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("Date and time", "Event type", "Title", "Details", "Record"))
    for event in context["events"]:
        writer.writerow((
            event["at"].isoformat(sep=" "),
            _csv_safe(event["type"]),
            _csv_safe(event["title"]),
            _csv_safe(event["detail"]),
            _csv_safe(event["link"]),
        ))
    # BOM helps Excel recognize the UTF-8 text in this user-owned download.
    payload = output.getvalue().encode("utf-8-sig")
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="tracker-health-timeline-{datetime.now():%Y%m%d}.csv"'
            ),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
