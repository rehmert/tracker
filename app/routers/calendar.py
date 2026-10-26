from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Protocol, DoseLog, Vial
from ..templating import render
from .. import calendar as cal

router = APIRouter()

@router.get('/calendar')
def calendar_page(request: Request, month: str = '', anchor: str = '', db: Session = Depends(get_db)):
    today = date.today()
    try:
        shown = date.fromisoformat(month + '-01') if month else today.replace(day=1)
        if not 2000 <= shown.year <= 2100: raise ValueError()
    except ValueError:
        shown = today.replace(day=1)
    try:
        start_anchor = date.fromisoformat(anchor) if anchor else shown
    except ValueError:
        start_anchor = shown
    first, end = cal.month_bounds(shown.year, shown.month)
    planned = {}
    for protocol in db.scalars(select(Protocol).where(Protocol.is_active.is_(True))):
        for item in protocol.items:
            # An anchor date is explicit, never inferred from the first recorded dose.
            for when in cal.occurrences(item, start_anchor, 400):
                if first <= when < end:
                    planned.setdefault(when, []).append({
                        'name': item.compound.name, 'protocol': protocol.name,
                        'dose': f'{item.amount_value:g} {item.amount_unit}'})
    actual = {}
    logs = db.scalars(select(DoseLog).join(Vial).where(
        DoseLog.kind == 'dose', DoseLog.taken_at >= datetime.combine(first, datetime.min.time()),
        DoseLog.taken_at < datetime.combine(end, datetime.min.time())).order_by(DoseLog.taken_at))
    for dose in logs:
        actual.setdefault(dose.taken_at.date(), []).append({
            'name': dose.vial.compound.name,
            'dose': f'{dose.entered_value:g} {dose.entered_unit}'})
    # Monday-first, including padding days for a calendar grid.
    grid_start = first - timedelta(days=first.weekday())
    grid_end = end + timedelta(days=(7-end.weekday()) % 7)
    days = []
    cursor = grid_start
    while cursor < grid_end:
        days.append({'date': cursor, 'in_month': first <= cursor < end,
                     'planned': planned.get(cursor, []), 'actual': actual.get(cursor, [])})
        cursor += timedelta(days=1)
    previous = first - timedelta(days=1)
    return render(request, 'calendar.html', days=days, shown=shown, anchor=start_anchor,
                  previous=previous.strftime('%Y-%m'), next_month=end.strftime('%Y-%m'))
