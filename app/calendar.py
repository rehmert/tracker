"""Read-only administration calendar. Projection is anchored to a user-selected date,
not an inferred start date. Never creates DoseLogs or consumes inventory.
"""
from datetime import date, timedelta
from calendar import monthrange
from math import isfinite

def occurrences(item, start: date, days: int = 35):
    """Project occurrences in [start, start+days), using frequency semantics from calc.py.
    An interval is every N days; day/week/month frequencies are N per period.
    Month uses an average 365.2425/12-day cadence, clearly an approximation.
    """
    if item.freq_count <= 0 or not isfinite(item.freq_count):
        return []
    if item.freq_period == 'interval':
        interval = item.freq_count
    else:
        periods = {'day': 1, 'week': 7, 'month': 365.2425/12}
        if item.freq_period not in periods: return []
        interval = periods[item.freq_period] / item.freq_count
    if interval < 1 / 24 or not isfinite(interval): return []
    result = []
    i = 0
    last = None
    while i * interval < days and i < 10000:
        day = start + timedelta(days=int(i * interval))
        if day != last:
            result.append(day)
            last = day
        i += 1
    return result

def staged_occurrences(item, protocol_start: date, days: int = 35):
    """Scheduled dates constrained to escalation weeks anchored at protocol start.

    Week 1 is [start, start+7 days); week N starts after 7*(N-1) days.
    An empty end_week means the stage continues indefinitely.
    """
    if days <= 0:
        return []
    first = protocol_start + timedelta(days=7 * (max(1, getattr(item, 'start_week', 1) or 1) - 1))
    stop = protocol_start + timedelta(days=days)
    if getattr(item, 'end_week', None) is not None:
        stop = min(stop, protocol_start + timedelta(days=7 * item.end_week))
    if first >= stop:
        return []
    dose_days = getattr(item, 'dose_days', None)
    if dose_days:
        weekdays = {int(v) for v in dose_days.split(',') if v.strip()}
        return [protocol_start + timedelta(days=offset)
                for offset in range((first - protocol_start).days, (stop - protocol_start).days)
                if (protocol_start + timedelta(days=offset)).weekday() in weekdays]
    # Preserve original frequency anchor at the protocol start, even across stages.
    return [day for day in occurrences(item, protocol_start, days) if first <= day < stop]

def month_bounds(year, month):
    first = date(year, month, 1)
    return first, first + timedelta(days=monthrange(year, month)[1])
