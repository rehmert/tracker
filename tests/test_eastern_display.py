from datetime import datetime, date, timezone
from app.templating import dt, utc_dt


def test_sqlite_utc_audit_winter_and_summer():
    assert utc_dt(datetime(2026, 1, 15, 17, 0)) == '2026-01-15 12:00 PM EST'
    assert utc_dt(datetime(2026, 7, 15, 16, 0)) == '2026-07-15 12:00 PM EDT'


def test_user_entered_wall_clock_preserved():
    assert dt(datetime(2026, 7, 15, 8, 30)) == '2026-07-15 08:30 AM EDT'
    assert dt(date(2026, 7, 15)) == '2026-07-15'


def test_aware_utc_backup_time_converts():
    assert dt(datetime(2026, 1, 15, 17, 0, tzinfo=timezone.utc)) == '2026-01-15 12:00 PM EST'
