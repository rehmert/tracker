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
    """Bounded local refinement around the highest sampled modeled exposure."""
    if not rows:
        raise ValueError('No model samples')
    values=[row['planned'] for row in rows]
    top=max(range(len(values)),key=values.__getitem__)
    best=values[top]
    for index in (top-1,top):
        if index<0 or index+1>=len(rows):
            continue
        start=datetime.fromisoformat(rows[index]['at'])
        finish=datetime.fromisoformat(rows[index+1]['at'])
        for fraction in (.125,.25,.375,.5,.625,.75,.875):
            time=start+(finish-start)*fraction
            best=max(best,pk.exposure_at(time,doses,elimination_hours,absorption_hours))
    return best
