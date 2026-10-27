"""Read-only dashboard schedule summary; does not create administrations."""
from datetime import date, datetime, timedelta
from .calendar import staged_occurrences
from .routers.calendar import reconcile


def schedule_summary(protocols, dose_logs, today: date, days_ahead: int = 7):
    """Today + next days; reconcile same-day compound records, one-to-one.

    Dose history is passed in separately to keep this function easy to test.
    Historical events are not inferred from an empty schedule.
    """
    end = today + timedelta(days=days_ahead)
    planned = {}
    missing_start = []
    for protocol in protocols:
        if not protocol.is_active:
            continue
        if protocol.start_date is None:
            missing_start.append({'id': protocol.id, 'name': protocol.name})
            continue
        if protocol.start_date > end or (protocol.end_date and protocol.end_date < today):
            continue
        horizon = (end - protocol.start_date).days + 1
        for item in protocol.items:
            for day in staged_occurrences(item, protocol.start_date, horizon):
                if today <= day <= end and (protocol.end_date is None or day <= protocol.end_date):
                    planned.setdefault(day, []).append({
                        'compound_id': item.compound_id, 'amount_value': item.amount_value, 'amount_unit': item.amount_unit,
                        'name': item.compound.name,
                        'protocol': protocol.name,
                        'dose': f'{item.amount_value:g} {item.amount_unit}',
                        'dose_time': getattr(item, 'dose_time', None) or '',
                        'fasting_hours': getattr(item, 'fasting_hours', None),
                    })
    actual = {}
    for dose in dose_logs:
        day = dose.taken_at.date()
        if day == today:
            actual.setdefault(day, []).append({
                'compound_id': dose.vial.compound_id,
                'name': dose.vial.compound.name,
                'dose': f'{dose.entered_value:g} {dose.entered_unit}',
            })
    reconciled = reconcile(planned, actual, today)
    today_events = reconciled.get(today, [])
    upcoming = [(day, event) for day in sorted(reconciled) if today < day <= end
                for event in reconciled[day] if event['status'] == 'upcoming']
    return {'today': today_events, 'upcoming': upcoming,
            'missing_start': missing_start}
