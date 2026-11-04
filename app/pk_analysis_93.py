"""Trapezoidal apparent-exposure statistics; not serum AUC."""
from datetime import datetime
from math import isfinite


def metrics(times, values):
    empty = {
        'auc_mg_equivalent_hours': None,
        'mean_mg_equivalent': None,
        'fluctuation_percent': None,
        'duration_hours': None,
    }

    if len(times) != len(values) or len(times) < 2:
        return empty

    points = [
        datetime.fromisoformat(t) for t in times
    ]

    if not all(
        isfinite(float(v)) and float(v) >= 0
        for v in values
    ):
        raise ValueError('Invalid modeled exposure')

    duration = 0.0
    auc = 0.0

    for i in range(1, len(points)):
        hours = (
            points[i] - points[i - 1]
        ).total_seconds() / 3600

        if hours <= 0:
            raise ValueError('Unsorted model timeline')

        auc += hours * (
            float(values[i - 1]) + float(values[i])
        ) / 2
        duration += hours

    avg = auc / duration

    return {
        'auc_mg_equivalent_hours': round(auc, 5),
        'mean_mg_equivalent': round(avg, 5),
        'fluctuation_percent': (
            round(
                100 * (
                    max(values) - min(values)
                ) / avg,
                3,
            )
            if avg > 0 else None
        ),
        'duration_hours': round(duration, 3),
    }
