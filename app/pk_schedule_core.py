"""Canonical read-only schedule projection for PK and inventory.

The calendar retains its date-oriented view. The core returns
exact naive wall-clock timestamps. It never records doses.
"""
from .pk_precision import schedule_doses as exact_schedule


def schedule_doses(
    protocol, compound_id, anchor_date, days,
    dose_multiplier=1.0, interval_multiplier=1.0,
):
    return exact_schedule(
        protocol, compound_id, anchor_date, days,
        dose_multiplier=dose_multiplier,
        interval_multiplier=interval_multiplier,
    )
