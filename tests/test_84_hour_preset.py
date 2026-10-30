from datetime import date
from types import SimpleNamespace
from app.calendar import occurrences, occurrence_time

def test_84_hour_dates_and_times():
    item = SimpleNamespace(freq_count=3.5, freq_period='interval', dose_time='08:00')
    start = date(2026, 11, 2)
    dates = occurrences(item, start, 15)
    assert dates[:4] == [date(2026,11,2),date(2026,11,5),date(2026,11,9),date(2026,11,12)]
    assert [occurrence_time(item, start, d) for d in dates[:4]] == ['08:00','20:00','08:00','20:00']
