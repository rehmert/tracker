"""Bounded PK sensitivity calculation and sub-grid modeled peak checks."""
from datetime import datetime, timedelta
from math import isfinite
from fastapi import HTTPException
from . import pk


def bounded_step(hours, initial_step, administrations, variants=9, budget=1800000):
    """Bound 9 * sample_count * administration_count; fail when too coarse."""
    if not all(isfinite(float(x)) and float(x)>0 for x in (hours,initial_step,budget)):
        raise HTTPException(400,'Invalid calculation budget')
    if administrations>500:
        raise HTTPException(413,'Too many administrations for interactive sensitivity analysis')
    step=max(float(initial_step),hours/3000, hours*variants*max(1,administrations)/budget)
    if step>24:
        raise HTTPException(413,'Sensitivity calculation exceeds interactive resolution budget')
    return step


def refined_peak(rows, doses, elimination_hours, absorption_hours):
    """Refine likely peak intervals across the full modeled window.

    This is bounded numerical refinement, not an exact analytic maximum.
    """
    if not rows:
        raise ValueError('No model samples')

    from bisect import bisect_right

    times=[
        datetime.fromisoformat(r['at'])
        for r in rows
    ]
    values=[r['planned'] for r in rows]

    if len(rows)==1:
        return values[0]

    # Prioritize intervals near sampled maxima and administration events.
    indices=set()

    for i in range(len(rows)-1):
        left=values[max(0,i-1)]
        right=values[min(len(values)-1,i+2)]
        if max(values[i],values[i+1])>=max(left,right):
            indices.add(i)

    for at,_ in doses:
        i=bisect_right(times,at)-1
        for nearby in (i-1,i,i+1):
            if 0<=nearby<len(times)-1:
                indices.add(nearby)

    # Fall back to intervals with the largest sampled values.
    ranked=sorted(
        range(len(times)-1),
        key=lambda i:max(values[i],values[i+1]),
        reverse=True
    )

    indices.update(ranked[:32])

    candidates=sorted(
        indices,
        key=lambda i:max(values[i],values[i+1]),
        reverse=True
    )[:64]

    best=max(values)

    for i in candidates:
        start=times[i]
        end=times[i+1]
        width=end-start

        for part in range(1,16):
            t=start+width*(part/16)
            best=max(
                best,
                pk.exposure_at(
                    t,doses,
                    elimination_hours,
                    absorption_hours
                )
            )

    return best
