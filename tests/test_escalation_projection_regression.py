from datetime import date
from types import SimpleNamespace
from app.calendar import staged_occurrences
from app.today import schedule_summary


def item(dose, start_week, end_week, weekdays=''):
    return SimpleNamespace(compound_id=1, compound=SimpleNamespace(name='Example'),
        amount_value=dose, amount_unit='mg', freq_count=1, freq_period='week',
        start_week=start_week, end_week=end_week, dose_days=weekdays,
        dose_time='08:00', fasting_hours=2)


def test_escalation_boundary_uses_protocol_start_date():
    start = date(2026, 10, 1)
    a = item(2.5, 1, 4)
    b = item(5, 5, 8)
    assert staged_occurrences(a, start, 70) == [date(2026, 10, 1), date(2026, 10, 8), date(2026, 10, 15), date(2026, 10, 22)]
    assert staged_occurrences(b, start, 70) == [date(2026, 10, 29), date(2026, 11, 5), date(2026, 11, 12), date(2026, 11, 19)]


def test_weekday_escalation_and_dashboard():
    start = date(2026, 10, 1)
    a = item(2.5, 1, 1, '0,2,4')
    b = item(5, 2, None, '0,2,4')
    assert staged_occurrences(a, start, 15) == [date(2026, 10, 2), date(2026, 10, 5), date(2026, 10, 7)]
    assert staged_occurrences(b, start, 15) == [date(2026, 10, 9), date(2026, 10, 12), date(2026, 10, 14)]
    protocol = SimpleNamespace(id=1, name='Escalation', is_active=True,
        start_date=start, end_date=None, items=[a, b])
    summary = schedule_summary([protocol], [], date(2026, 10, 9), 5)
    assert [e['dose'] for e in summary['today']] == ['5 mg']
    assert all(e['dose'] == '5 mg' for _, e in summary['upcoming'])
