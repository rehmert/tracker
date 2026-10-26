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

def month_bounds(year, month):
    first = date(year, month, 1)
    return first, first + timedelta(days=monthrange(year, month)[1])
