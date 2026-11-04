"""PK plotter-style offsets and per-stage cadence, without data writes."""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError
from jinja2 import Environment
from pathlib import Path

from app.routers.pk import WhatIfProtocol, what_if_doses

ROOT = Path(__file__).resolve().parents[1]


def schedule(**updates):
    data = dict(
        compound_id=1,
        name="Model only",
        start_at=datetime(2026, 11, 1, 9),
        interval_days=7,
        duration_days=35,
        half_life_hours=120,
        absorption_half_life_hours=12,
        stages=[{"week": 1, "amount_mg": 5}],
    )
    data.update(updates)
    return WhatIfProtocol(**data)


def test_backward_compatibility_default_offset_and_interval():
    doses = what_if_doses(schedule())
    assert len(doses) == 5
    assert [d[0].day for d in doses] == [1, 8, 15, 22, 29]
    assert all(amount == 5 for _, amount in doses)


def test_first_dose_offset():
    doses = what_if_doses(schedule(offset_days=2, duration_days=24))
    assert doses[0][0] == datetime(2026, 11, 3, 9)
    assert doses[1][0] == datetime(2026, 11, 10, 9)
    assert doses[2][0] == datetime(2026, 11, 17, 9)


def test_midcourse_dose_and_frequency_change():
    data = schedule(
        duration_days=28,
        stages=[
            {"week": 1, "amount_mg": 5},
            {"week": 3, "amount_mg": 7.5, "interval_days": 3.5},
        ],
    )
    doses = what_if_doses(data)
    days = [(at - data.start_at).total_seconds() / 86400 for at, _ in doses]
    assert days == [0, 7, 14, 17.5, 21, 24.5]
    assert [dose for _, dose in doses] == [5, 5, 7.5, 7.5, 7.5, 7.5]


def test_stage_can_inherit_default_again():
    data = schedule(
        duration_days=35,
        stages=[
            {"week": 1, "amount_mg": 5, "interval_days": 3.5},
            {"week": 3, "amount_mg": 6, "interval_days": None},
        ],
    )
    doses = what_if_doses(data)
    assert doses[0][0] == data.start_at
    assert any(
        at == data.start_at + timedelta(days=14) and amount == 6
        for at, amount in doses
    )
    assert any(
        at == data.start_at + timedelta(days=21) and amount == 6
        for at, amount in doses
    )


def test_offset_keeps_stage_weeks_relative_to_first_dose():
    data = schedule(
        offset_days=3,
        duration_days=32,
        stages=[
            {"week": 1, "amount_mg": 5},
            {"week": 3, "amount_mg": 8},
        ],
    )
    doses = what_if_doses(data)
    assert [a for _, a in doses] == [5, 5, 8, 8, 8]


@pytest.mark.parametrize("updates", [
    {"offset_days": -1},
    {"offset_days": 91},
    {"offset_days": 7, "duration_days": 7},
    {"offset_days": 3.5},
    {"stages": [{"week": 1, "amount_mg": 5, "interval_days": 0}]},
    {"stages": [{"week": 1, "amount_mg": 5, "interval_days": 91}]},
    {"stages": [{"week": 1, "amount_mg": 5, "interval_days": float("nan")}]},
])
def test_invalid_offsets_or_stage_intervals_are_rejected(updates):
    with pytest.raises(ValidationError):
        schedule(**updates)


def test_preview_and_save_share_schedule_function():
    router = (ROOT / "app/routers/pk.py").read_text()
    assert "schedule = what_if_doses(data)" in router
    assert "for at, amount in what_if_doses(data)" in router
    assert "db.commit()" in router


def test_template_and_client_are_wired():
    html = (ROOT / "app/templates/pk.html").read_text()
    js = (ROOT / "app/static/pk.js").read_text()

    for marker in (
        'id="wiOffset"',
        "Interval (days; blank = default)",
        "pk.js?v=pk-batch41-20261104",
    ):
        assert marker in html

    for marker in (
        "className='wiCadence'",
        "offset_days:offset",
        "interval_days:tr.querySelector('.wiCadence').value.trim()",
        "const duration=Number($('wiDuration').value);",
    ):
        assert marker in js

    Environment().parse(html)
