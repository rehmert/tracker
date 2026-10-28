from datetime import datetime
import pytest
from pydantic import ValidationError
from app.routers.pk import WhatIfProtocol, what_if_doses


def data(**changes):
    values = dict(compound_id=1, name='Hypothetical', start_at=datetime(2026, 11, 1, 9),
                  interval_days=7, duration_days=28, half_life_hours=120,
                  absorption_half_life_hours=24,
                  stages=[{'week': 1, 'amount_mg': 1}, {'week': 3, 'amount_mg': 2}])
    values.update(changes)
    return WhatIfProtocol(**values)


def test_staged_recurring_doses():
    doses = what_if_doses(data())
    assert [d[1] for d in doses] == [1, 1, 2, 2]
    assert [d[0].day for d in doses] == [1, 8, 15, 22]


def test_rejects_duplicate_or_missing_week_one():
    for stages in ([{'week': 2, 'amount_mg': 1}],
                   [{'week': 1, 'amount_mg': 1}, {'week': 1, 'amount_mg': 2}]):
        with pytest.raises(ValidationError):
            data(stages=stages)


def test_interval_and_duration():
    doses = what_if_doses(data(interval_days=3, duration_days=10))
    assert len(doses) == 4
