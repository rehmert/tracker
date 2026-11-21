"""Release 731: user-entered tablet quantities, calculated without floats.

This module is arithmetic and validation only. It does not recommend splitting
a tablet, change prescriptions, or alter pill/supply inventory.
"""
from decimal import Decimal, InvalidOperation
import re

STEP = Decimal("0.25")
MAX_TABLETS = Decimal("20")
MAX_MG = Decimal("10000")
PRECISION = Decimal("0.001")


def number(raw, label, *, maximum=MAX_MG):
    value = str(raw or "").strip()
    if not value or len(value) > 24:
        raise ValueError(label + " is required.")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError(label + " must be a valid number.") from None
    if not result.is_finite() or result <= 0 or result > maximum or (
        result.quantize(PRECISION) != result
    ):
        raise ValueError(label + " must be positive, finite, and have at most 3 decimal places.")
    return result


def tablets(raw):
    result = number(raw, "Number of tablets", maximum=MAX_TABLETS)
    if result % STEP:
        raise ValueError("Use a whole, half, or quarter-tablet quantity.")
    return result


def format_number(raw):
    value = format(Decimal(str(raw)), "f")
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    return value


def amount(tablet_count, administered_mg):
    count = format_number(tablet_count)
    word = "tablet" if Decimal(str(tablet_count)) == 1 else "tablets"
    return count + " " + word + " (" + format_number(administered_mg) + " mg)"


def schedule_values(strength_raw, prescribed_raw, tablets_raw):
    strength = number(strength_raw, "Tablet strength")
    prescribed = number(prescribed_raw, "Prescribed dose")
    quantity = tablets(tablets_raw)
    if strength * quantity != prescribed:
        raise ValueError(
            "Prescribed dose must equal tablet strength × planned tablets. "
            "Check the doctor's order and pill quantity."
        )
    return dict(
        tablet_strength_mg=strength,
        prescribed_dose_mg=prescribed,
        tablets_planned=quantity,
    )


def entry_values(strength_raw, prescribed_raw, tablets_raw):
    strength = number(strength_raw, "Tablet strength")
    prescribed = number(prescribed_raw, "Prescribed dose")
    quantity = tablets(tablets_raw)
    calculated = strength * quantity
    if calculated > MAX_MG or calculated.quantize(PRECISION) != calculated:
        raise ValueError("Calculated dose is outside the supported range.")
    return dict(
        tablet_strength_mg=strength,
        prescribed_dose_mg=prescribed,
        tablets_taken=quantity,
        administered_dose_mg=calculated,
    )


def catalog_tablet_strength(raw):
    """Only an unambiguous milligram-per-tablet label may seed the UI."""
    match = re.fullmatch(
        r"\s*(\d+(?:\.\d{1,3})?)\s*mg(?:\s*(?:/|per)\s*tablet)?\s*",
        str(raw or ""), flags=re.IGNORECASE,
    )
    if not match:
        return ""
    try:
        return format_number(number(match.group(1), "Tablet strength"))
    except ValueError:
        return ""
