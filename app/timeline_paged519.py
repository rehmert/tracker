"""Bounded SQL pagination for the unsearched Health Timeline.

The existing Python materialization path remains the reference implementation
for free-text search and full CSV export. This module applies identical date
ranges and stable ordering without loading entire event histories.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta
from itertools import groupby

from fastapi import HTTPException
from sqlalchemy import String, case, cast, func, literal, select, union_all
from sqlalchemy.orm import Session, selectinload

from . import config, metrics
from .models import DoseLog, LabReport, Protocol, Vial, VitalReading


def _event_index(since: datetime | None, through: datetime | None):
    """Build one SQL index row per event; payloads are loaded only for a page."""
    def link(prefix, column, suffix=""):
        return literal(prefix) + cast(column, String) + literal(suffix)

    vital = select(
        literal("vital").label("source"),
        VitalReading.id.label("event_id"),
        cast(VitalReading.measured_at, String).label("occurred"),
        literal("Vital").label("kind"),
        link("/vitals/", VitalReading.id, "/edit").label("link"),
        literal("").label("tie"),
    )
    if since is not None:
        vital = vital.where(VitalReading.measured_at >= since)
    if through is not None:
        vital = vital.where(VitalReading.measured_at <= through)

    dose = select(
        literal("dose").label("source"),
        DoseLog.id.label("event_id"),
        cast(DoseLog.taken_at, String).label("occurred"),
        case((DoseLog.kind == "dose", "Dose"), else_="Waste").label("kind"),
        link("/doses/", DoseLog.id, "/edit").label("link"),
        literal("").label("tie"),
    )
    if since is not None:
        dose = dose.where(DoseLog.taken_at >= since)
    if through is not None:
        dose = dose.where(DoseLog.taken_at <= through)

    # Date-only entries are displayed at midnight in the original timeline.
    midnight = literal(" 00:00:00.000000")
    lab = select(
        literal("lab").label("source"),
        LabReport.id.label("event_id"),
        (cast(LabReport.drawn_on, String) + midnight).label("occurred"),
        literal("Lab").label("kind"),
        link("/labs/", LabReport.id).label("link"),
        literal("").label("tie"),
    )
    if since is not None:
        lab = lab.where(LabReport.drawn_on >= since.date())
    if through is not None:
        lab = lab.where(LabReport.drawn_on <= through.date())

    def plan_event(source, field, tie):
        q = select(
            literal(source).label("source"),
            Protocol.id.label("event_id"),
            (cast(field, String) + midnight).label("occurred"),
            literal("Protocol").label("kind"),
            link("/protocols/", Protocol.id).label("link"),
            literal(tie).label("tie"),
        ).where(Protocol.is_active.is_(True), field.is_not(None))
        if since is not None:
            q = q.where(field >= since.date())
        if through is not None:
            q = q.where(field <= through.date())
        return q

    return union_all(
        vital,
        dose,
        lab,
        plan_event("protocol-start", Protocol.start_date, "start"),
        plan_event("protocol-end", Protocol.end_date, "end"),
    ).subquery("timeline_index519")


def _hydrate_page(db: Session, keys):
    """Batch ORM reads per event kind, preserving index ordering exactly."""
    wanted = {}
    for row in keys:
        wanted.setdefault(row.source.split("-", 1)[0], set()).add(row.event_id)

    loaded = {}
    if wanted.get("vital"):
        stmt = select(VitalReading).where(
            VitalReading.id.in_(wanted["vital"])
        )
        loaded["vital"] = {obj.id: obj for obj in db.scalars(stmt)}
    if wanted.get("dose"):
        stmt = select(DoseLog).options(
            selectinload(DoseLog.vial).selectinload(Vial.compound)
        ).where(DoseLog.id.in_(wanted["dose"]))
        loaded["dose"] = {obj.id: obj for obj in db.scalars(stmt)}
    if wanted.get("lab"):
        stmt = select(LabReport).options(
            selectinload(LabReport.results)
        ).where(LabReport.id.in_(wanted["lab"]))
        loaded["lab"] = {obj.id: obj for obj in db.scalars(stmt)}
    if wanted.get("protocol"):
        stmt = select(Protocol).where(
            Protocol.id.in_(wanted["protocol"])
        )
        loaded["protocol"] = {obj.id: obj for obj in db.scalars(stmt)}

    events = []
    for row in keys:
        source = row.source
        obj = loaded[source.split("-", 1)[0]][row.event_id]
        if source == "vital":
            parts = []
            if obj.weight_kg is not None:
                parts.append(
                    f"Weight {metrics.weight_from_kg(obj.weight_kg, config.WEIGHT_UNIT):.1f} {config.WEIGHT_UNIT}"
                )
            if obj.systolic is not None:
                parts.append(f"BP {obj.systolic}/{obj.diastolic or '—'}")
            if obj.pulse_bpm is not None:
                parts.append(f"Pulse {obj.pulse_bpm} bpm")
            events.append(dict(
                at=obj.measured_at, type="Vital", title=" · ".join(parts),
                detail=" · ".join(filter(None, (obj.context, obj.notes))),
                link=f"/vitals/{obj.id}/edit",
            ))
        elif source == "dose":
            events.append(dict(
                at=obj.taken_at,
                type="Dose" if obj.kind == "dose" else "Waste",
                title=f"{obj.vial.compound.name}: {obj.entered_value:g} {obj.entered_unit}",
                detail=" · ".join(filter(None, (obj.site, obj.notes))),
                link=f"/doses/{obj.id}/edit",
            ))
        elif source == "lab":
            events.append(dict(
                at=datetime.combine(obj.drawn_on, time.min),
                type="Lab",
                title=f"{obj.lab_name or 'Lab report'} · {len(obj.results)} results",
                detail=obj.notes, link=f"/labs/{obj.id}",
            ))
        else:
            beginning = source == "protocol-start"
            events.append(dict(
                at=datetime.combine(obj.start_date if beginning else obj.end_date, time.min),
                type="Protocol",
                title=f"{obj.name} · {'start date' if beginning else 'end date'}",
                detail=(
                    "Scheduled protocol start, not a confirmed administration"
                    if beginning else "Scheduled protocol end"
                ),
                link=f"/protocols/{obj.id}",
            ))
    return events


def paged_timeline_context(
    db: Session, *,
    days: int,
    event_type: str,
    start_date: date | None,
    end_date: date | None,
    page: int,
    page_size: int,
    ranges,
    event_types,
):
    """Paginate without loading out-of-page event objects into Python."""
    days = days if days in ranges else 90
    event_type = event_type if event_type in event_types else "all"
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

    index = _event_index(since, through)
    counts = Counter(dict(
        db.execute(
            select(index.c.kind, func.count())
            .group_by(index.c.kind)
        ).all()
    ))
    total = sum(counts.values())
    matching = total if event_type == "all" else counts[event_type]
    page_size = page_size if page_size in (25, 50, 100) else 50
    total_pages = max(1, (matching + page_size - 1) // page_size)
    page = min(max(1, page), total_pages)
    first = (page - 1) * page_size

    query = select(
        index.c.source, index.c.event_id
    )
    if event_type != "all":
        query = query.where(index.c.kind == event_type)
    query = query.order_by(
        index.c.occurred.desc(),
        index.c.kind.desc(),
        index.c.link.desc(),
        index.c.tie.desc(),
    ).offset(first).limit(page_size)

    events = _hydrate_page(db, db.execute(query).all())
    return dict(
        events=events,
        groups=[
            {"day": day, "events": list(day_events)}
            for day, day_events in groupby(
                events, key=lambda event: event["at"].date()
            )
        ],
        days=days, ranges=ranges,
        event_type=event_type, event_types=event_types,
        q="", total=total, counts=counts,
        start_date=start_date, end_date=end_date,
        page=page, page_size=page_size,
        total_pages=total_pages, matching=matching,
        page_start=first + 1 if matching else 0,
        page_end=first + len(events),
    )
