from datetime import date
from sqlalchemy import create_engine, inspect, text
from app.migrations import migrate
from app.routers.calendar import reconcile


def test_reconcile_matched_unmatched_and_past():
    day = date(2026, 10, 20)
    planned = {day: [dict(compound_id=1, name='A', dose='5 mg', protocol='P'),
                     dict(compound_id=2, name='B', dose='2 mg', protocol='P')]}
    actual = {day: [dict(compound_id=1, name='A', dose='5 mg'),
                    dict(compound_id=3, name='C', dose='1 mg')]}
    result = reconcile(planned, actual, date(2026, 10, 26))[day]
    assert [event['status'] for event in result] == ['recorded', 'unrecorded', 'extra']


def test_reconcile_does_not_reuse_recording():
    day = date(2026, 10, 20)
    planned = {day: [dict(compound_id=1), dict(compound_id=1)]}
    actual = {day: [dict(compound_id=1, dose='1 mg')]}
    result = reconcile(planned, actual, date(2026, 10, 26))[day]
    assert [x['status'] for x in result] == ['recorded', 'unrecorded']


def test_migration_adds_dates_idempotently():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE protocols (id INTEGER PRIMARY KEY, name VARCHAR(160), is_active BOOLEAN NOT NULL DEFAULT 0)'))
    migrate(engine)
    migrate(engine)
    columns = {c['name'] for c in inspect(engine).get_columns('protocols')}
    assert {'start_date', 'end_date'}.issubset(columns)
