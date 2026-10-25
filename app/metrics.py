"""Body-metric helpers (weight, blood pressure, pulse). Pure Python.

Descriptive only: this module stores, converts and averages what you enter.
It does not label readings as normal, high or low. The validation limits below
exist to catch typos (a missing digit, swapped fields), not to judge a result.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

KG_PER_LB = 0.45359237
WEIGHT_UNITS = ("kg", "lb")


def weight_to_kg(value: float, unit: str) -> float:
    unit = unit.strip().lower()
    if unit == "kg":
        return value
    if unit in ("lb", "lbs"):
        return value * KG_PER_LB
    raise ValueError(f"Unknown weight unit '{unit}'.")


def weight_from_kg(kg: float | None, unit: str) -> float | None:
    if kg is None:
        return None
    return kg if unit.strip().lower() == "kg" else kg / KG_PER_LB


# Typo guards only (physically possible ranges, not health ranges).
LIMITS = {"weight_kg": (20.0, 500.0), "systolic": (50, 300), "diastolic": (20, 200),
          "pulse": (20, 300)}


def validate(weight_kg: float | None, systolic: int | None, diastolic: int | None,
             pulse: int | None) -> list[str]:
    errs: list[str] = []
    if weight_kg is None and systolic is None and diastolic is None and pulse is None:
        return ["Enter at least one value (weight, blood pressure or pulse)."]
    if weight_kg is not None and not LIMITS["weight_kg"][0] <= weight_kg <= LIMITS["weight_kg"][1]:
        errs.append("That weight looks like a typo (outside 20 to 500 kg).")
    if (systolic is None) != (diastolic is None):
        errs.append("Enter both blood pressure numbers (top and bottom), or neither.")
    if systolic is not None and diastolic is not None:
        if not LIMITS["systolic"][0] <= systolic <= LIMITS["systolic"][1]:
            errs.append("The top blood pressure number looks like a typo (outside 50 to 300).")
        if not LIMITS["diastolic"][0] <= diastolic <= LIMITS["diastolic"][1]:
            errs.append("The bottom blood pressure number looks like a typo (outside 20 to 200).")
        if diastolic >= systolic:
            errs.append("The top number should be larger than the bottom one. Are they swapped?")
    if pulse is not None and not LIMITS["pulse"][0] <= pulse <= LIMITS["pulse"][1]:
        errs.append("That pulse looks like a typo (outside 20 to 300 bpm).")
    return errs


@dataclass
class Summary:
    n: int = 0
    latest: float | None = None
    latest_at: datetime | None = None
    avg7: float | None = None
    avg30: float | None = None
    min30: float | None = None
    max30: float | None = None
    change30: float | None = None   # last minus first reading inside the 30-day window


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def summarize(points: list[tuple[datetime, float]], now: datetime | None = None) -> Summary:
    """Plain descriptive stats. Averages are per reading, not per day."""
    now = now or datetime.now()
    pts = sorted(points)
    s = Summary(n=len(pts))
    if not pts:
        return s
    s.latest_at, s.latest = pts[-1]
    last7 = [v for t, v in pts if t >= now - timedelta(days=7)]
    win30 = [(t, v) for t, v in pts if t >= now - timedelta(days=30)]
    last30 = [v for _, v in win30]
    s.avg7, s.avg30 = _mean(last7), _mean(last30)
    if last30:
        s.min30, s.max30 = min(last30), max(last30)
    if len(win30) >= 2:
        s.change30 = win30[-1][1] - win30[0][1]
    return s
