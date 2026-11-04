from datetime import date,time
from pathlib import Path
from app.pk_calendar_schedule149 import (
    CalendarRule,project
)


def test_weekdays():
    rule=CalendarRule(
        start=date(2026,11,2),
        end=date(2026,11,9),
        weekdays=[0,3],
        local_time=time(8),
        amount_mg=1
    )

    result=project(rule)
    assert len(result['doses'])==3
    assert not result['warnings']


def test_dst_gap():
    rule=CalendarRule(
        start=date(2026,3,8),
        end=date(2026,3,8),
        weekdays=[6],
        local_time=time(2,30),
        amount_mg=1
    )

    assert project(rule)['warnings']


def test_eight_stage_support():
    s=Path(
        'app/static/js/tracker-pk-calendar149.js'
    ).read_text()
    assert 'extra.children.length>=6' in s
