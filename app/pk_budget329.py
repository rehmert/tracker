"""Shared computational guard for reference and optimized PK engines."""

from math import ceil, isfinite

MAX_SAMPLES = 20001
MAX_REFERENCE_WORK = 8_000_000


def validate_series_budget(
    start, end, actual, planned, step_hours
):
    hours = (end - start).total_seconds() / 3600

    if not 0 < hours <= 730 * 24:
        raise ValueError('Invalid modeled window')

    if not isfinite(step_hours) or not .01 <= step_hours <= 168:
        raise ValueError('Invalid graph resolution')

    # Conservative around floating-point step boundaries.
    samples = ceil(hours / step_hours) + 1

    if samples > MAX_SAMPLES:
        raise ValueError(
            'PK calculation exceeds sample budget'
        )

    if (
        samples * (len(actual) + len(planned))
        > MAX_REFERENCE_WORK
    ):
        raise ValueError(
            'PK calculation exceeds operation budget'
        )

    return samples
