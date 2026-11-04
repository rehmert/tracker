from datetime import date
from types import SimpleNamespace
from app.pk_precision import (
    schedule_doses, interval_assessment,
)


def protocol(interval):
    item = SimpleNamespace(
        compound_id=1, amount_value=5,
        amount_unit="mg", freq_count=interval,
        freq_period="interval", start_week=1,
        end_week=None, dose_days="",
        dose_time="08:00"
    )
    return SimpleNamespace(items=[item])


def test_84_hour_intervals_are_exact():
    doses = schedule_doses(
        protocol(3.5),1,date(2026,11,1),14
    )
    assert len(doses) == 4
    assert all(
        (b[0]-a[0]).total_seconds() == 84*3600
        for a,b in zip(doses,doses[1:])
    )
    assert doses[0][0].hour == 8
    assert doses[1][0].hour == 20


def test_half_day_schedule_does_not_collapse_dates():
    doses = schedule_doses(
        protocol(0.5),1,date(2026,11,1),3
    )
    assert len(doses) == 6


def test_stages_keep_original_anchor():
    p = protocol(3.5)
    first = p.items[0]
    second = SimpleNamespace(**vars(first))
    first.end_week = 1
    second.start_week = 2
    second.amount_value = 10
    p.items.append(second)
    doses = schedule_doses(p,1,date(2026,11,1),14)
    assert len(doses) == 4
    assert [amount for _,amount in doses] == [
        5,5,10,10
    ]


def test_irregular_stability_not_overclaimed():
    assert interval_assessment([],[])["status"] == \
        "Not assessable"
