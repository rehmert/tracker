"""Unit handling. Pure Python, no framework imports.

Amounts live in one of three dimensions, each with a base unit used for storage
and arithmetic:

    mass    -> mcg
    volume  -> mL
    iu      -> IU   (International Units; NOT convertible to mass without a
                     product-specific potency, so it is its own dimension)

A vial is tracked in either mass (mcg) or IU. Doses may also be entered as a
volume (mL / uL); that is converted through the vial's concentration.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


class UnitError(ValueError):
    """Raised when a unit is unknown or a conversion is not possible."""


@dataclass(frozen=True)
class Unit:
    name: str      # canonical display name
    dim: str       # "mass" | "volume" | "iu"
    factor: float  # multiply by this to reach the dimension's base unit


BASE_UNIT = {"mass": "mcg", "volume": "mL", "iu": "IU"}

_UNITS: dict[str, Unit] = {}


def _reg(dim: str, name: str, factor: float, *aliases: str) -> None:
    unit = Unit(name, dim, factor)
    for key in (name, *aliases):
        _UNITS[key.lower()] = unit


_reg("mass", "mcg", 1.0, "ug", "µg", "μg")
_reg("mass", "mg", 1_000.0)
_reg("mass", "g", 1_000_000.0)
_reg("volume", "mL", 1.0, "cc")
_reg("volume", "uL", 0.001, "µl", "μl")
_reg("iu", "IU", 1.0)

CONTENT_UNITS = ["mcg", "mg", "g", "IU"]     # what a vial can contain
DOSE_UNITS = ["mcg", "mg", "g", "IU", "mL", "uL"]  # what a dose can be entered in


def parse_unit(text: str) -> Unit:
    key = (text or "").strip().lower()
    if key not in _UNITS:
        raise UnitError(f"Unknown unit '{text}'.")
    return _UNITS[key]


def to_base(value: float, unit: str) -> tuple[float, str]:
    """Return (value in the dimension's base unit, dimension)."""
    u = parse_unit(unit)
    return value * u.factor, u.dim


def from_base(base_value: float, unit: str) -> float:
    return base_value / parse_unit(unit).factor


def convert(value: float, from_unit: str, to_unit: str) -> float:
    a, b = parse_unit(from_unit), parse_unit(to_unit)
    if a.dim != b.dim:
        raise UnitError(f"Can't convert {a.name} ({a.dim}) to {b.name} ({b.dim}).")
    return value * a.factor / b.factor


def concentration(content_base: float, volume_ml: float | None) -> float | None:
    """Base units per mL (mcg/mL or IU/mL), or None if volume is unknown."""
    if not volume_ml or volume_ml <= 0:
        return None
    return content_base / volume_ml


def amount_to_vial_base(value: float, unit: str, vial_dim: str,
                        conc_per_ml: float | None) -> float:
    """Convert an entered amount into a vial's base unit.

    Same-dimension amounts convert directly. Volumes are converted using the
    vial's concentration. Anything else (e.g. mg against an IU vial) is refused
    rather than guessed.
    """
    u = parse_unit(unit)
    if u.dim == vial_dim:
        return value * u.factor
    if u.dim == "volume":
        if not conc_per_ml:
            raise UnitError(
                "A volume can only be converted when the vial has a known volume "
                "(reconstitute it first, or enter its liquid volume)."
            )
        return value * u.factor * conc_per_ml
    raise UnitError(
        f"{u.name} can't be converted here: this compound is tracked in "
        f"{BASE_UNIT[vial_dim]}."
    )


def ml_to_syringe_units(ml: float, units_per_ml: float = 100.0) -> float:
    """Graduation marks on a U-100 insulin syringe (100 marks = 1 mL).
    Pure arithmetic on a volume you already chose; not a dosing suggestion."""
    return ml * units_per_ml


def _num(x: float, digits: int = 4) -> str:
    if x == 0:
        return "0"
    mag = math.floor(math.log10(abs(x)))
    decimals = max(0, digits - 1 - mag)
    s = f"{x:.{decimals}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def fmt_amount(base: float | None, dim: str | None, digits: int = 4) -> str:
    """Human-readable amount from a base value, choosing a sensible unit."""
    if base is None or dim is None:
        return "—"
    if dim == "mass":
        a = abs(base)
        if a >= 1_000_000:
            return f"{_num(base / 1_000_000, digits)} g"
        if a >= 1_000:
            return f"{_num(base / 1_000, digits)} mg"
        return f"{_num(base, digits)} mcg"
    if dim == "iu":
        return f"{_num(base, digits)} IU"
    if dim == "volume":
        return f"{_num(base, digits)} mL" if abs(base) >= 1 else f"{_num(base * 1000, digits)} uL"
    raise UnitError(f"Unknown dimension '{dim}'.")


def fmt_conc(conc_per_ml: float | None, dim: str | None) -> str:
    if conc_per_ml is None or dim is None:
        return "—"
    if dim == "iu":
        return f"{_num(conc_per_ml)} IU/mL"
    if conc_per_ml >= 1_000:
        return f"{_num(conc_per_ml / 1_000)} mg/mL"
    return f"{_num(conc_per_ml)} mcg/mL"
