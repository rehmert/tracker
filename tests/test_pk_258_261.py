from datetime import datetime,timedelta
import random

from app import pk
from app.pk_fast261 import series_fast


def test_recurrence_matches_independent_reference():
    start=datetime(2026,11,4)
    rng=random.Random(127)

    cases=[
        (120,12),
        (2.4,.65),
        (1,1),
        (.183333,.05),
        (120,120),
        (192,24)
    ]

    for hl,absorb in cases:
        events=[
            (
                start+timedelta(
                    hours=rng.uniform(-96,70)
                ),
                rng.uniform(.1,5)
            )
            for _ in range(25)
        ]

        actual=events[:12]
        planned=events[12:]

        reference=pk.series(
            start,
            start+timedelta(hours=80),
            actual,planned,
            hl,absorb,
            step_hours=.5
        )

        fast=series_fast(
            start,
            start+timedelta(hours=80),
            actual,planned,
            hl,absorb,
            step_hours=.5
        )

        assert len(reference)==len(fast)

        assert all(
            abs(a['planned']-b['planned'])<.00011
            and abs(a['actual']-b['actual'])<.00011
            for a,b in zip(reference,fast)
        )
