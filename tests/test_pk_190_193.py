from datetime import datetime,timedelta
import pytest

from app import pk
from app.pk_alignment193 import (
    shared_step,validate_alignment
)
from app.pk_metrics181 import metrics


def test_short_half_life_grid_is_shared():
    step=shared_step(2)
    assert step==.5

    start=datetime(2026,11,4)
    doses=[(start,2)]

    curves=[
        pk.series(
            start,
            start+timedelta(days=2),
            [],
            doses,
            2*f,
            .5,
            step_hours=step
        )
        for f in (.75,1.,1.25)
    ]

    times=validate_alignment(curves)

    assert all(
        len(curve)==len(times)
        for curve in curves
    )

    assert all(
        curve[0]['at']==times[0]
        for curve in curves
    )


def test_mismatched_grids_fail():
    with pytest.raises(
        ValueError,match='not identical'
    ):
        validate_alignment([
            [{'at':'2026-11-04T00:00:00'}],
            [{'at':'2026-11-04T00:30:00'}]
        ])


def test_trapezoidal_reference():
    rows=[
        {
            'at':'2026-11-04T00:00:00',
            'planned':0
        },
        {
            'at':'2026-11-04T01:00:00',
            'planned':10
        },
        {
            'at':'2026-11-04T04:00:00',
            'planned':10
        }
    ]

    assert metrics(rows)['auc']==35
    assert metrics(rows)['mean']==8.75
