from datetime import datetime,timedelta

from app import pk
from app.pk_precision225 import refined_peak,bounded_step


def test_multiple_peaks_are_checked():
    start=datetime(2026,11,4)
    doses=[
        (start,3),
        (start+timedelta(hours=30),7)
    ]

    rows=pk.series(
        start,
        start+timedelta(hours=72),
        [],
        doses,
        8,
        1,
        step_hours=12
    )

    sampled=max(r['planned'] for r in rows)
    refined=refined_peak(rows,doses,8,1)

    assert refined>=sampled

    dense=max(
        pk.exposure_at(
            start+timedelta(minutes=15*i),
            doses,8,1
        )
        for i in range(72*4+1)
    )

    # Bounded refinement must approach dense sampling closely.
    assert abs(refined-dense)<.15


def test_calculation_budget_is_bounded():
    step=bounded_step(
        24*60,.5,400
    )
    assert step>=.5
    assert step<=24
