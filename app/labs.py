"""Lab-result helpers: analyte naming, unit conversion for a few common analytes,
series building and printed-range comparison. Pure Python.

Nothing here judges a result. "Below / within / above printed range" only compares
a number with the range that was printed on the lab's own report.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time

COMMON_ANALYTES = [
    "Total testosterone", "Free testosterone", "SHBG", "Estradiol", "LH", "FSH", "Prolactin",
    "DHEA-S", "IGF-1", "TSH", "Free T4", "Free T3", "Hemoglobin", "Hematocrit", "RBC", "WBC",
    "Platelets", "PSA", "ALT", "AST", "Creatinine", "eGFR", "BUN", "Glucose", "HbA1c", "Insulin",
    "Total cholesterol", "HDL cholesterol", "LDL cholesterol", "Triglycerides", "Ferritin",
    "Vitamin D", "CRP", "Sodium", "Potassium",
]

# canonical key -> accepted spellings (all compared lower case)
_ALIASES = {
    "testosterone": ["testosterone", "total testosterone", "testosterone, total", "testosterone total"],
    "estradiol": ["estradiol", "e2", "estradiol (e2)", "estradiol, sensitive"],
    "glucose": ["glucose", "fasting glucose", "blood glucose"],
    "total cholesterol": ["total cholesterol", "cholesterol", "cholesterol, total"],
    "hdl cholesterol": ["hdl", "hdl cholesterol", "hdl-c"],
    "ldl cholesterol": ["ldl", "ldl cholesterol", "ldl-c"],
    "triglycerides": ["triglycerides", "triglyceride"],
    "creatinine": ["creatinine", "serum creatinine"],
    "hemoglobin": ["hemoglobin", "haemoglobin", "hgb"],
    "igf-1": ["igf-1", "igf1", "igf-i", "igf 1"],
}
_LOOKUP = {alias: key for key, names in _ALIASES.items() for alias in names}

# (from_unit, to_unit) -> multiplier, per canonical analyte; the reverse is derived.
_FACTORS = {
    "testosterone": {("ng/dl", "nmol/l"): 0.03467},
    "estradiol": {("pg/ml", "pmol/l"): 3.671},
    "glucose": {("mg/dl", "mmol/l"): 1 / 18.016},
    "total cholesterol": {("mg/dl", "mmol/l"): 1 / 38.67},
    "hdl cholesterol": {("mg/dl", "mmol/l"): 1 / 38.67},
    "ldl cholesterol": {("mg/dl", "mmol/l"): 1 / 38.67},
    "triglycerides": {("mg/dl", "mmol/l"): 1 / 88.57},
    "creatinine": {("mg/dl", "umol/l"): 88.4},
    "hemoglobin": {("g/dl", "g/l"): 10.0},
    "igf-1": {("ng/ml", "nmol/l"): 0.131},
}


def analyte_key(name: str) -> str:
    n = re.sub(r"\s+", " ", (name or "").strip().lower())
    return _LOOKUP.get(n, n)


def norm_unit(unit: str) -> str:
    return re.sub(r"\s+", "", (unit or "").lower().replace("µ", "u").replace("μ", "u"))


def convert(analyte: str, value: float, from_unit: str, to_unit: str) -> float | None:
    """Value in `to_unit`, or None when no known conversion exists."""
    a, b = norm_unit(from_unit), norm_unit(to_unit)
    if a == b:
        return value
    table = _FACTORS.get(analyte_key(analyte), {})
    if (a, b) in table:
        return value * table[(a, b)]
    if (b, a) in table:
        return value / table[(b, a)]
    return None


@dataclass
class Point:
    when: date
    value: float
    unit: str
    ref_low: float | None = None
    ref_high: float | None = None


@dataclass
class SeriesResult:
    unit: str
    points: list[tuple[datetime, float]]
    skipped: int                                 # results in units that can't be converted
    band: tuple[float, float] | None


def at_noon(d: date) -> datetime:
    return datetime.combine(d, time(12))


def build_series(analyte: str, pts: list[Point]) -> SeriesResult:
    """Chart in the unit of the newest result, converting older ones where a known
    conversion exists and counting those that can't be converted."""
    pts = sorted(pts, key=lambda p: p.when)
    if not pts:
        return SeriesResult("", [], 0, None)
    target = pts[-1].unit
    out, skipped = [], 0
    for p in pts:
        v = convert(analyte, p.value, p.unit, target)
        if v is None:
            skipped += 1
        else:
            out.append((at_noon(p.when), v))
    band = None
    for p in reversed(pts):
        if p.ref_low is not None and p.ref_high is not None:
            lo = convert(analyte, p.ref_low, p.unit, target)
            hi = convert(analyte, p.ref_high, p.unit, target)
            if lo is not None and hi is not None:
                band = (lo, hi)
            break
    return SeriesResult(target, out, skipped, band)


def range_status(value: float, low: float | None, high: float | None) -> str | None:
    """'below' / 'within' / 'above' the range printed on the report, or None."""
    if low is None or high is None:
        return None
    if value < low:
        return "below"
    if value > high:
        return "above"
    return "within"
