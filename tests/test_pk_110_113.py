from datetime import datetime
from app.pk_scenario_ops import (
    SequenceInput, preview, fingerprint
)


def test_intervals_and_fingerprint():
    values=preview(SequenceInput(
        start_at=datetime(2026,11,4,8),
        amount_mg=2.5,
        interval_days=.5,
        count=3,
    ))

    assert [
        x['planned_at'][-8:] for x in values
    ] == [
        '08:00:00',
        '20:00:00',
        '08:00:00',
    ]

    assert len(fingerprint([]))==64
