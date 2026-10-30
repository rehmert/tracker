"""Calendar view: reconciles recorded doses with projected protocol dates.
Never writes dose logs or changes inventory. Reconciliation is a same-day,
same-compound association; it does not claim clinical equivalence of amounts.
"""
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from sqlalchemy import select
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Protocol, ProtocolItem, ProjectionExclusion, DoseLog, Vial
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
                events.append(dict(p, status='recorded', actual_dose=recordings[matched]['dose']))
            else:
                status = 'unrecorded' if day < today else ('due' if day == today else 'upcoming')
                events.append(dict(p, status=status, actual_dose=None))
        for idx, a in enumerate(recordings):
            if idx not in used:
                events.append(dict(a, status='extra'))
        result[day] = events
    return result


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
    events = reconcile(planned, actual, today)
    return first, end, events, missing_start


@router.get('/calendar')
def calendar_page(request: Request, month: str = '', db: Session = Depends(get_db)):
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
    return render(request, 'calendar.html', days=days, shown=shown,
                  exclusions=list(db.scalars(select(ProjectionExclusion).order_by(ProjectionExclusion.scheduled_on.desc(), ProjectionExclusion.id.desc()))),
                  missing_start=missing_start,
                  previous=previous.strftime('%Y-%m'), next_month=end.strftime('%Y-%m'))


@router.post('/calendar/exclude')
def exclude_projection(protocol_item_id: int = Form(...), scheduled_on: date = Form(...),
                       scope: str = Form('once'), reason: str = Form(''),
                       db: Session = Depends(get_db)):
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
def restore_projection(exclusion_id: int, db: Session = Depends(get_db)):
    rule = db.get(ProjectionExclusion, exclusion_id)
    if rule is None:
        raise HTTPException(404, 'Exclusion not found')
    month = rule.scheduled_on.strftime('%Y-%m')
    db.delete(rule)
    db.commit()
    return RedirectResponse(f'/calendar?month={month}', status_code=303)


def _ical_escape(value: object) -> str:
    return (str(value).replace('\\', '\\\\').replace('\n', '\\n')
            .replace(',', '\\,').replace(';', '\\;'))


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
def export_calendar_ics(month: str = '', db: Session = Depends(get_db)):
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
