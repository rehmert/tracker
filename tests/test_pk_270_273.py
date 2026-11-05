from datetime import datetime,timedelta
from random import Random
from time import perf_counter
from app import pk
from app.pk_fast261 import series_fast


def test_boundary_and_near_equal_rate_agreement():
    start=datetime(2026,11,4,8)
    random=Random(270)
    for hl,absorb in (
        (120,12),(12,12),(12,12.000001),
        (2.4,.65),(.183333,.05),(192,24)
    ):
        events=[
            (
                start+timedelta(
                    minutes=random.randint(-9000,3000)
                ),
                random.uniform(.1,4)
            )
            for _ in range(40)
        ]
        events.extend([
            (start,1),
            (start+timedelta(hours=1),2),
            (start+timedelta(hours=1,minutes=1),3)
        ])
        args=(
            start,start+timedelta(days=3),
            events[:20],events[20:],
            hl,absorb
        )
        a=pk.series(*args,step_hours=.5)
        b=series_fast(*args,step_hours=.5)
        assert len(a)==len(b)
        assert all(
            x['at']==y['at']
            and abs(x['planned']-y['planned'])<.00012
            and abs(x['actual']-y['actual'])<.00012
            for x,y in zip(a,b)
        )


def test_interactive_calculation_budget():
    from app.pk_precision225 import bounded_step
    step=bounded_step(720,.5,400)
    assert .5<=step<=24

    start=datetime(2026,11,4)
    events=[
        (start+timedelta(hours=i*6),1.)
        for i in range(100)
    ]
    begin=perf_counter()
    result=series_fast(
        start,start+timedelta(days=30),
        events,[],120,12,step_hours=6
    )
    assert result
    assert perf_counter()-begin<20
