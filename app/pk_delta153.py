"""Aligned trapezoidal statistics; no drug-effect inference."""
from math import isfinite
from datetime import datetime
from fastapi import HTTPException


def delta(at,left,right):
    if (
        len(at)<2
        or len(left)!=len(at)
        or len(right)!=len(at)
    ):
        raise HTTPException(
            400,'Non-aligned model series'
        )

    times=[
        datetime.fromisoformat(x) for x in at
    ]

    difference=[
        b-a for a,b in zip(left,right)
    ]

    if not all(
        isfinite(x) for x in difference
    ):
        raise HTTPException(
            400,'Non-finite modeled exposure'
        )

    hours=[
        (
            times[i]-times[i-1]
        ).total_seconds()/3600
        for i in range(1,len(times))
    ]

    if not all(v>0 for v in hours):
        raise HTTPException(
            400,'Non-monotonic timeline'
        )

    area=sum(
        (
            difference[i]+difference[i-1]
        )*h/2
        for i,h in enumerate(hours,1)
    )

    duration=sum(hours)

    return {
        'difference':difference,
        'mean_delta':area/duration,
        'auc_delta':area,
        'max_delta':max(difference),
        'min_delta':min(difference),
        'units':'modeled mg-equivalent exposure'
    }
