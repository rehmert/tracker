"""Read-only timeline of recorded health events and active protocol milestones."""
import csv
import io
from collections import Counter
from datetime import date, datetime, timedelta, time
from itertools import groupby

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, metrics
from ..scoped_db390 import get_scoped_db390
from ..models import VitalReading, DoseLog, LabReport, Protocol
from ..templating import render

router = APIRouter()
# The "All" option retains its existing value for bookmarked URLs but no
# longer imposes an arbitrary ten-year cutoff.
RANGES = {7: "7 days", 30: "30 days", 90: "90 days", 180: "6 months", 365: "1 year", 3650: "All", 0: "Custom dates"}
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
    start_date: date | None = None,
    end_date: date | None = None,
):
    """One read-only source for both on-screen entries and CSV exports."""
    days = days if days in RANGES else 90
    event_type = event_type if event_type in EVENT_TYPES else "all"
    q = q.strip()[:100]
    search = q.casefold()

    # Explicit dates take precedence over presets. A one-sided date boundary
    # is intentionally unbounded on the other side.
    if start_date is not None or end_date is not None:
        days = 0
    if days == 0:
        if start_date and end_date and start_date > end_date:
            raise HTTPException(400, "From date must not be after through date.")
        since = datetime.combine(start_date, time.min) if start_date else None
        through = datetime.combine(end_date, time.max) if end_date else None
    else:
        since = None if days == 3650 else datetime.now() - timedelta(days=days)
        through = None

    events = []

    vital_query = select(VitalReading)
    if since is not None:
        vital_query = vital_query.where(VitalReading.measured_at >= since)
    if through is not None:
        vital_query = vital_query.where(VitalReading.measured_at <= through)
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
    if through is not None:
        dose_query = dose_query.where(DoseLog.taken_at <= through)
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
    if through is not None:
        report_query = report_query.where(LabReport.drawn_on <= through.date())
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
        if (protocol.start_date
                and (since is None or protocol.start_date >= since.date())
                and (through is None or protocol.start_date <= through.date())):
            events.append(dict(
                at=datetime.combine(protocol.start_date, time.min),
                type="Protocol", title=f"{protocol.name} · start date",
                detail="Scheduled protocol start, not a confirmed administration",
                link=f"/protocols/{protocol.id}",
            ))
        if (protocol.end_date
                and (since is None or protocol.end_date >= since.date())
                and (through is None or protocol.end_date <= through.date())):
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
    events.sort(
        key=lambda event: (
            event["at"], event["type"], event["link"], event["title"]
        ),
        reverse=True,
    )
    groups = [
        {"day": day, "events": list(day_events)}
        for day, day_events in groupby(events, key=lambda event: event["at"].date())
    ]
    return dict(
        events=events, groups=groups,
        days=days, ranges=RANGES, event_type=event_type, event_types=EVENT_TYPES,
        q=q, total=total, counts=counts,
        start_date=start_date, end_date=end_date,
    )


@router.get("/health-timeline")
def timeline(
    request: Request,
    days: int = 90,
    event_type: str = "all",
    q: str = "",
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_scoped_db390),
):
    context = _timeline_context(
        db, days=days, event_type=event_type, q=q,
        start_date=start_date, end_date=end_date,
    )
    matching = len(context["events"])
    page_size = page_size if page_size in (25, 50, 100) else 50
    total_pages = max(1, (matching + page_size - 1) // page_size)
    page = min(max(1, page), total_pages)
    first = (page - 1) * page_size
    visible = context["events"][first:first + page_size]
    context.update(
        events=visible,
        groups=[
            {"day": day, "events": list(day_events)}
            for day, day_events in groupby(
                visible, key=lambda event: event["at"].date()
            )
        ],
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        matching=matching,
        page_start=first + 1 if matching else 0,
        page_end=first + len(visible),
    )
    return render(request, "health_timeline.html", **context)


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
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_scoped_db390),
):
    """Download exactly the entries shown by the selected timeline filters."""
    context = _timeline_context(
        db, days=days, event_type=event_type, q=q,
        start_date=start_date, end_date=end_date,
    )
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
