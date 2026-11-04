from datetime import datetime,timedelta

from app.pk import series
from app.pk_alignment193 import validate_alignment
from app.pk_metrics181 import metrics


def test_nine_variants_share_timeline_and_envelope():
    start=datetime(2026,11,4)
    planned=[(start,1)]

    curves=[]

    for elimination in (.75,1.,1.25):
        for absorption in (.75,1.,1.25):
            rows=series(
                start,
                start+timedelta(days=2),
                [],
                planned,
                120*elimination,
                12*absorption,
                step_hours=1
            )
            curves.append(rows)

    times=validate_alignment(curves)

    assert len(curves)==9
    assert len(times)==49

    for i in range(len(times)):
        vals=[
            row[i]['planned']
            for row in curves
        ]

        assert (
            min(vals)
            <=curves[4][i]['planned']
            <=max(vals)
        )

    assert metrics(curves[4])['auc']>0
