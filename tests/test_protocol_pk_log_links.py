from datetime import date, datetime, timedelta
from types import SimpleNamespace
from app.routers.pk import protocol_planned_doses
from app.today import schedule_summary


def test_pk_projection_respects_escalation_week_and_time():
    start = date(2026, 10, 1)
    compound = SimpleNamespace(name='Tirzepatide')
    first = SimpleNamespace(compound_id=5, amount_value=2.5, amount_unit='mg', start_week=1, end_week=4, dose_days='3', dose_time='08:30', freq_count=1, freq_period='week')
    second = SimpleNamespace(compound_id=5, amount_value=5, amount_unit='mg', start_week=5, end_week=8, dose_days='3', dose_time='08:30', freq_count=1, freq_period='week')
    protocol = SimpleNamespace(start_date=start, end_date=None, is_active=True, items=[first, second])
    class FakeDB:
        def get(self, model, id):
            return protocol
    rows = protocol_planned_doses(FakeDB(), 1, 5, datetime(2026,10,1), datetime(2026,11,12))
    assert (datetime(2026,10,22,8,30),2.5) in rows
    assert (datetime(2026,10,29,8,30),5) in rows
    assert (datetime(2026,10,29,8,30),2.5) not in rows


def test_dashboard_events_include_log_link_prefill_fields():
    item = SimpleNamespace(compound_id=5, compound=SimpleNamespace(name='Example'), amount_value=5, amount_unit='mg', start_week=1, end_week=None, dose_days='0', dose_time='09:00', fasting_hours=2, freq_count=1, freq_period='week')
    protocol = SimpleNamespace(id=1,name='Protocol',is_active=True,start_date=date(2026,10,26),end_date=None,items=[item])
    result = schedule_summary([protocol],[],date(2026,10,26))
    assert result['today'][0]['amount_value'] == 5
    assert result['today'][0]['amount_unit'] == 'mg'
    assert result['today'][0]['dose_time'] == '09:00'
