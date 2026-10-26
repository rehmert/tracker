from datetime import date
from types import SimpleNamespace
from app.calendar import occurrences, month_bounds
from app.labs import convert

def test_calendar_weekly():
    item = SimpleNamespace(freq_count=1, freq_period='week')
    assert occurrences(item, date(2026, 10, 1), 22) == [date(2026, 10, 1),date(2026, 10, 8),date(2026, 10, 15),date(2026, 10, 22)]

def test_calendar_interval():
    item = SimpleNamespace(freq_count=3.5, freq_period='interval')
    assert len(occurrences(item, date(2026, 10, 1), 14)) == 4

def test_calendar_invalid():
    assert occurrences(SimpleNamespace(freq_count=0, freq_period='week'), date.today()) == []

def test_month_bounds():
    assert month_bounds(2028,2) == (date(2028,2,1),date(2028,3,1))

def test_lab_comparison_conversion():
    assert abs(convert('testosterone', 10, 'nmol/L', 'ng/dL') - 288.43) < 0.2
