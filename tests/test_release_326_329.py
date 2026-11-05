from datetime import datetime, timedelta

import pytest

from app import pk
from app.pk_fast261 import series_fast
from app.pk_budget329 import validate_series_budget


def test_both_engines_reject_oversized_sample_windows():
    start = datetime(2026, 11, 4)
    end = start + timedelta(days=100)

    for runner in (pk.series, series_fast):
        with pytest.raises(
            ValueError,
            match='sample budget'
        ):
            runner(
                start, end,
                [], [],
                120, 12,
                step_hours=.01
            )


def test_both_engines_agree_with_normal_intervals():
    start = datetime(2026, 11, 4, 8)
    end = start + timedelta(days=6)

    doses = [
        (start - timedelta(days=2), 2.5),
        (start + timedelta(days=1), 2.5)
    ]

    reference = pk.series(
        start, end,
        doses, [],
        120, 12,
        step_hours=3
    )

    fast = series_fast(
        start, end,
        doses, [],
        120, 12,
        step_hours=3
    )

    assert len(reference) == len(fast)

    assert all(
        abs(a['planned'] - b['planned']) < .00012
        for a, b in zip(reference, fast)
    )


def test_budget_rejects_reference_work_explosion():
    start = datetime(2026, 11, 4)
    end = start + timedelta(days=30)

    doses = [(start, 1)] * 5000

    with pytest.raises(
        ValueError,
        match='operation budget'
    ):
        validate_series_budget(
            start, end,
            doses, [],
            .25
        )
