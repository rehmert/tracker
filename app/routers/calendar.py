"""Calendar view: reconciles recorded doses with projected protocol dates.
Never writes dose logs or changes inventory. Reconciliation is a same-day,
same-compound association; it does not claim clinical equivalence of amounts.
"""
from datetime import date, datetime, timedelta, timezone
import csv
from io import StringIO
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from sqlalchemy import select
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session, selectinload
from ..scoped_db390 import get_scoped_db390
from ..models import Protocol, ProtocolItem, ProjectionExclusion, DoseLog, Vial, Blend, BlendDose, BlendComponent
from ..blend_administration_view import blend_dose_components
from ..projection_exclusions import exclusions_for, excluded
from ..templating import render
from .. import calendar as cal

router = APIRouter()


def reconcile(planned, actual, today):
    """Match each recorded dose to at most one same-day planned occurrence.

    A matching record is displayed as 'recorded', while unmatched past
    projections are 'unrecorded' (not a clinical assertion of a missed dose).
    """
    result = {}
    for day in sorted(set(planned) | set(actual)):
        events = []
        recordings = list(actual.get(day, []))
        used = set()
        for p in planned.get(day, []):
            matched = next((idx for idx, a in enumerate(recordings)
                            if idx not in used and a['compound_id'] == p['compound_id']), None)
            if matched is not None:
                used.add(matched)
                # Preserve the source blend only when the matched recording
                # actually originated from a prepared blend.
                events.append(dict(
                    p, status='recorded',
                    actual_dose=recordings[matched]['dose'],
                    actual_blend_id=recordings[matched].get('blend_id'),
                ))
            else:
                status = 'unrecorded' if day < today else ('due' if day == today else 'upcoming')
                events.append(dict(p, status=status, actual_dose=None))
        for idx, a in enumerate(recordings):
            if idx not in used:
                events.append(dict(a, status='extra'))
        result[day] = events
    return result


def calendar_status_counts(days: list[dict]) -> dict[str, int]:
    """Count current-month entries only; never alters reconciliation or records."""
    counts = dict.fromkeys(("due", "upcoming", "unrecorded", "recorded", "extra"), 0)
    for day in days:
        if not day["in_month"]:
            continue
        for event in day["events"]:
            status = event.get("status")
            if status in counts:
                counts[status] += 1
    return counts



_REVIEW_STATUSES = frozenset(("unrecorded", "due", "upcoming"))


def calendar_review_items(days: list[dict]) -> list[dict]:
    """Chronological, display-only projected entries requiring review.

    A missing matching log is not proof an administration was missed.
    Outside-month grid cells and already-matched logs are excluded.
    """
    items = [
        {"date": day["date"], "event": event}
        for day in days if day["in_month"]
        for event in day["events"]
        if event.get("status") in _REVIEW_STATUSES
    ]
    return sorted(items, key=lambda item: (
        item["date"],
        item["event"].get("dose_time") or "",
        (item["event"].get("name") or "").casefold(),
        (item["event"].get("protocol") or "").casefold(),
        item["event"].get("protocol_item_id") or 0,
    ))


def _calendar_csv_safe(value: object) -> str:
    """Prevent spreadsheet formulas in free-text CSV cells."""
    text = "" if value is None else str(value)
    stripped = text.lstrip()
    if stripped.startswith(("=", "+", "-", "@")) or (text and text[0].isspace()):
        return "'" + text
    return text


def _parse_month(month: str) -> date:
    today = date.today()
    try:
        shown = date.fromisoformat(month + '-01') if month else today.replace(day=1)
        if not 2000 <= shown.year <= 2100:
            raise ValueError()
    except ValueError:
        shown = today.replace(day=1)
    return shown


def _month_events(shown: date, db: Session):
    today = date.today()
    first, end = cal.month_bounds(shown.year, shown.month)
    planned = {}
    protocols = list(db.scalars(select(Protocol).where(Protocol.is_active.is_(True))))
    rules = exclusions_for(db, [item.id for protocol in protocols for item in protocol.items])
    missing_start = []
    for protocol in protocols:
        if protocol.start_date is None:
            missing_start.append({'id': protocol.id, 'name': protocol.name})
            continue
        if protocol.start_date >= end or (protocol.end_date and protocol.end_date < first):
            continue
        days_to_project = (end - protocol.start_date).days
        for item in protocol.items:
            for when in cal.staged_occurrences(item, protocol.start_date, days_to_project):
                if first <= when < end and (protocol.end_date is None or when <= protocol.end_date) and not excluded(rules, item.id, when):
                    planned.setdefault(when, []).append({
                        'protocol_item_id': item.id, 'compound_id': item.compound_id, 'amount_value': item.amount_value, 'amount_unit': item.amount_unit,
                        'name': item.compound.name, 'protocol': protocol.name,
                        'dose': f'{item.amount_value:g} {item.amount_unit}',
                        'dose_time': cal.occurrence_time(item, protocol.start_date, when), 'fasting_hours': item.fasting_hours})
    actual = {}
    logs = db.scalars(select(DoseLog).join(Vial).where(
        DoseLog.kind == 'dose',
        DoseLog.taken_at >= datetime.combine(first, datetime.min.time()),
        DoseLog.taken_at < datetime.combine(end, datetime.min.time())
    ).order_by(DoseLog.taken_at))
    for dose in logs:
        actual.setdefault(dose.taken_at.date(), []).append({
            'compound_id': dose.vial.compound_id,
            'name': dose.vial.compound.name,
            'dose': f'{dose.entered_value:g} {dose.entered_unit}'})
    # Blend draws are stored separately from ordinary vial DoseLogs.
    # One administered draw contributes a recorded occurrence for each
    # constituent compound, but never creates duplicate DoseLog rows.
    blend_draws = db.scalars(
        select(BlendDose)
        .where(
            BlendDose.kind == 'dose',
            BlendDose.taken_at >= datetime.combine(first, datetime.min.time()),
            BlendDose.taken_at < datetime.combine(end, datetime.min.time()),
        )
        .options(
            selectinload(BlendDose.blend)
            .selectinload(Blend.components)
            .selectinload(BlendComponent.compound),
            selectinload(BlendDose.blend)
            .selectinload(Blend.components)
            .selectinload(BlendComponent.source_vial),
        )
        .order_by(BlendDose.taken_at, BlendDose.id)
    )
    for draw in blend_draws:
        for component in blend_dose_components(draw):
            actual.setdefault(draw.taken_at.date(), []).append({
                'compound_id': component['compound_id'],
                'name': component['name'],
                'dose': f"{component['amount']:g} {component['unit']} (blend #{draw.blend_id})",
                'dose_time': draw.taken_at.strftime('%H:%M'),
                'blend_id': draw.blend_id,
            })
    events = reconcile(planned, actual, today)
    return first, end, events, missing_start


@router.get('/calendar')
def calendar_page(request: Request, month: str = '', db: Session = Depends(get_scoped_db390)):
    shown = _parse_month(month)
    first, end, events, missing_start = _month_events(shown, db)
    grid_start = first - timedelta(days=(first.weekday() + 1) % 7)
    grid_end = end + timedelta(days=(7 - ((end.weekday() + 1) % 7)) % 7)
    days = []
    cursor = grid_start
    while cursor < grid_end:
        days.append({'date': cursor, 'in_month': first <= cursor < end,
                     'events': events.get(cursor, [])})
        cursor += timedelta(days=1)
    previous = first - timedelta(days=1)
    status_counts = calendar_status_counts(days)
    review_items = calendar_review_items(days)
    return render(request, 'calendar.html', days=days, shown=shown,
                  today=date.today(), status_counts=status_counts,
                  review_items=review_items,
                  calendar_total=sum(status_counts.values()),
                  exclusions=list(db.scalars(select(ProjectionExclusion).order_by(ProjectionExclusion.scheduled_on.desc(), ProjectionExclusion.id.desc()))),
                  missing_start=missing_start,
                  previous=previous.strftime('%Y-%m'), next_month=end.strftime('%Y-%m'))


@router.get('/calendar/review.csv')
def export_calendar_review_csv(month: str = '', db: Session = Depends(get_scoped_db390)):
    """Export only projected review entries; never changes protocols or logs."""
    shown = _parse_month(month)
    first, end, events, _ = _month_events(shown, db)
    days = [
        {'date': day, 'in_month': first <= day < end, 'events': entries}
        for day, entries in events.items()
    ]
    items = calendar_review_items(days)
    labels = {
        'unrecorded': 'No matching log',
        'due': 'Due today',
        'upcoming': 'Upcoming',
    }
    output = StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(('Date', 'Time', 'Status', 'Protocol', 'Compound',
                     'Planned amount', 'Unit'))
    for item in items:
        event = item['event']
        writer.writerow((
            item['date'].isoformat(),
            _calendar_csv_safe(event.get('dose_time')),
            labels[event['status']],
            _calendar_csv_safe(event.get('protocol')),
            _calendar_csv_safe(event.get('name')),
            _calendar_csv_safe(event.get('amount_value')),
            _calendar_csv_safe(event.get('amount_unit')),
        ))
    return Response(
        content=output.getvalue().encode('utf-8-sig'),
        media_type='text/csv',
        headers={'Content-Disposition':
                 f'attachment; filename="tracker-calendar-review-{shown:%Y-%m}.csv"'},
    )


@router.post('/calendar/exclude')
def exclude_projection(protocol_item_id: int = Form(...), scheduled_on: date = Form(...),
                       scope: str = Form('once'), reason: str = Form(''),
                       db: Session = Depends(get_scoped_db390)):
    if scope not in ('once', 'onward'):
        raise HTTPException(400, 'Invalid exclusion scope')
    item = db.get(ProtocolItem, protocol_item_id)
    if item is None or item.protocol.start_date is None:
        raise HTTPException(404, 'Protocol schedule not found')
    if scheduled_on < item.protocol.start_date:
        raise HTTPException(400, 'Date precedes protocol start')
    # An exclusion must target a real occurrence, preventing accidental broad suppression.
    if scheduled_on not in cal.staged_occurrences(item, item.protocol.start_date,
                                                   (scheduled_on - item.protocol.start_date).days + 1):
        raise HTTPException(400, 'Date is not a scheduled occurrence for this protocol item')
    existing = db.scalar(select(ProjectionExclusion).where(
        ProjectionExclusion.protocol_item_id == protocol_item_id,
        ProjectionExclusion.scheduled_on == scheduled_on,
        ProjectionExclusion.scope == scope))
    if existing is None:
        db.add(ProjectionExclusion(protocol_item_id=protocol_item_id, scheduled_on=scheduled_on,
                                   scope=scope, reason=reason[:255]))
        db.commit()
    return RedirectResponse(f'/calendar?month={scheduled_on:%Y-%m}', status_code=303)


@router.post('/calendar/exclusions/{exclusion_id}/restore')
def restore_projection(exclusion_id: int, db: Session = Depends(get_scoped_db390)):
    rule = db.get(ProjectionExclusion, exclusion_id)
    if rule is None:
        raise HTTPException(404, 'Exclusion not found')
    month = rule.scheduled_on.strftime('%Y-%m')
    db.delete(rule)
    db.commit()
    return RedirectResponse(f'/calendar?month={month}', status_code=303)


def _ical_escape(value: object) -> str:
    """Escape iCalendar TEXT, including CR-only and CRLF newlines.

    Untrusted note/protocol fields must never introduce a raw content line.
    """
    text = str(value).replace('\\', '\\\\')
    return (text.replace('\r\n', '\n').replace('\r', '\n')
            .replace('\n', '\\n').replace(',', '\\,').replace(';', '\\;'))


def _ical_line(value: str) -> str:
    """Fold at 75 UTF-8 octets, per RFC 5545."""
    result = []
    line = ''
    for ch in value:
        if len((line + ch).encode('utf-8')) > 75:
            result.append(line)
            line = ' ' + ch
        else:
            line += ch
    result.append(line)
    return '\r\n'.join(result)


@router.get('/calendar/export.ics')
def export_calendar_ics(month: str = '', db: Session = Depends(get_scoped_db390)):
    """Download a snapshot of the displayed month's calendar events; no writes."""
    shown = _parse_month(month)
    first, end, events, _ = _month_events(shown, db)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Tracker//Protocol Calendar//EN',
             'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
             'X-WR-CALNAME:Tracker Protocol Calendar']
    for day in sorted(events):
        for index, event in enumerate(events[day]):
            name = event.get('name', 'Dose')
            status = event['status']
            summary = f"{name} · {event.get('dose', '')} ({status})"
            description = f"Protocol: {event.get('protocol', 'Unmatched recorded dose')}\nStatus: {status}"
            if event.get('fasting_hours') is not None:
                description += f"\nFasting hours: {event['fasting_hours']}"
            uid = f"tracker-{day:%Y%m%d}-{event.get('protocol_item_id', 'log')}-{index}@local"
            lines.extend(['BEGIN:VEVENT', f'UID:{uid}', f'DTSTAMP:{stamp}',
                          f'SUMMARY:{_ical_escape(summary)}',
                          f'DESCRIPTION:{_ical_escape(description)}'])
            clock = event.get('dose_time')
            if clock:
                try:
                    t = datetime.strptime(clock, '%H:%M').time()
                    dt = datetime.combine(day, t)
                    lines.extend([f'DTSTART;TZID=America/New_York:{dt:%Y%m%dT%H%M%S}',
                                  f'DTEND;TZID=America/New_York:{(dt + timedelta(minutes=15)):%Y%m%dT%H%M%S}'])
                except ValueError:
                    clock = None
            if not clock:
                lines.extend([f'DTSTART;VALUE=DATE:{day:%Y%m%d}',
                              f'DTEND;VALUE=DATE:{(day + timedelta(days=1)):%Y%m%d}'])
            lines.append('END:VEVENT')
    lines.append('END:VCALENDAR')
    payload = '\r\n'.join(_ical_line(line) for line in lines) + '\r\n'
    return Response(content=payload.encode('utf-8'), media_type='text/calendar',
                    headers={'Content-Disposition': f'attachment; filename="tracker-calendar-{shown:%Y-%m}.ics"'})
