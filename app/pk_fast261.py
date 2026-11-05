"""O(samples + doses) PK recurrence.

The original app.pk.series remains the independent numerical
reference implementation.
"""
from datetime import timedelta
from math import exp,isfinite
from . import pk


def series_fast(
    start,end,actual,planned,
    half_life_hours,
    absorption_half_life_hours,
    step_hours=12
):
    if end<=start or (end-start).days>730:
        raise ValueError('Invalid modeled window')

    if not isfinite(step_hours) or not .01<=step_hours<=168:
        raise ValueError('Invalid step')

    if not all(
        isfinite(x) and x>0
        for x in (
            half_life_hours,
            absorption_half_life_hours
        )
    ):
        raise ValueError('Invalid half-life')

    ke=pk.LN2/half_life_hours
    ka=pk.LN2/absorption_half_life_hours
    near=abs(ka-ke)<1e-10

    def prepare(doses):
        ordered=sorted(
            doses,key=lambda d:d[0]
        )

        for _,amount in ordered:
            if not isfinite(amount) or amount<=0:
                raise ValueError('Invalid dose')

        return ordered

    groups=[
        prepare(actual),
        prepare(planned)
    ]

    indices=[0,0]

    # Exponential response terms at the current sample.
    state=[
        [0.,0.,0.]
        for _ in range(2)
    ]

    last=start
    output=[]
    t=start

    while t<=end:
        delta=(t-last).total_seconds()/3600

        decay_e=exp(-ke*delta)
        decay_a=exp(-ka*delta)

        for i,events in enumerate(groups):
            se,sa,weighted=state[i]

            weighted=(
                weighted+delta*se
            )*decay_e

            se*=decay_e
            sa*=decay_a

            while (
                indices[i]<len(events)
                and events[indices[i]][0]<=t
            ):
                when,amount=events[indices[i]]

                h=(t-when).total_seconds()/3600

                if h>=0:
                    e=exp(-ke*h)

                    se+=amount*e
                    sa+=amount*exp(-ka*h)
                    weighted+=amount*h*e

                indices[i]+=1

            state[i]=[
                se,sa,weighted
            ]

        def response(values):
            se,sa,weighted=values

            if near:
                result=ka*weighted
            else:
                result=ka/(ka-ke)*(se-sa)

            return max(0.,result)

        baseline=response(state[0])
        modeled=baseline+response(state[1])

        output.append({
            'at':t.isoformat(),
            'actual':round(baseline,5),
            'planned':round(modeled,5)
        })

        last=t
        t+=timedelta(hours=step_hours)

    return output
