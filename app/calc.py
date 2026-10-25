"""Cost / inventory / protocol arithmetic. Pure Python (no DB, no framework).

Money is carried as float *cents* inside calculations (allocation produces
fractions of a cent) and rounded only for display.

Nothing here recommends a dose. Every function takes numbers the user entered
and returns arithmetic on them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import units as U

PERIOD_DAYS = {"day": 1.0, "week": 7.0, "month": 365.25 / 12}
PERIOD_LABELS = {
    "day": "per day",
    "week": "per week",
    "month": "per month",
    "interval": "(once every N days)",
}
MONTH_DAYS = PERIOD_DAYS["month"]
ACTIVE_STATUSES = ("sealed", "in_use")


# ---------------------------------------------------------------- purchases
def allocate_landed(prices_cents: dict[int, int], shipping: int, tax: int,
                    discount: int) -> dict[int, float]:
    """Spread shipping + tax - discount across a purchase's vials, pro rata by
    price (equally if every price is zero). Returns landed cents per vial id."""
    if not prices_cents:
        return {}
    extra = shipping + tax - discount
    total = sum(prices_cents.values())
    n = len(prices_cents)
    out = {}
    for vid, price in prices_cents.items():
        share = price / total if total > 0 else 1 / n
        out[vid] = max(price + extra * share, 0.0)
    return out


# -------------------------------------------------------------------- vials
@dataclass
class VialData:
    id: int
    compound_id: int
    dim: str                    # "mass" | "iu"
    content_base: float         # effective content (label, or COA if opted in)
    volume_ml: float | None
    status: str
    landed_cents: float
    consumed_base: float = 0.0

    @property
    def remaining_base(self) -> float:
        return max(self.content_base - self.consumed_base, 0.0)

    @property
    def over_base(self) -> float:
        return max(self.consumed_base - self.content_base, 0.0)

    @property
    def pct_remaining(self) -> float:
        if self.content_base <= 0:
            return 0.0
        return 100.0 * self.remaining_base / self.content_base

    @property
    def conc_per_ml(self) -> float | None:
        return U.concentration(self.content_base, self.volume_ml)

    @property
    def cost_per_base(self) -> float:
        return self.landed_cents / self.content_base if self.content_base > 0 else 0.0

    @property
    def remaining_value_cents(self) -> float:
        return self.remaining_base * self.cost_per_base


def dose_cost_cents(vial: VialData, amount_base: float) -> float:
    return amount_base * vial.cost_per_base


# ---------------------------------------------------------------- compounds
@dataclass
class CompoundRef:
    """Inventory and pricing reference for one compound, derived from its vials."""
    compound_id: int
    name: str
    dim: str | None = None
    conc_per_ml: float | None = None
    cost_per_base: float | None = None       # cents per base unit
    on_hand_base: float = 0.0
    typical_vial_base: float | None = None   # most recent vial's content
    typical_vial_cents: float | None = None  # most recent vial's landed cost
    actual_per_week_base: float | None = None


def build_compound_ref(compound_id: int, name: str, vials: list[VialData],
                       logged_28d_base: float = 0.0) -> CompoundRef:
    ref = CompoundRef(compound_id, name, actual_per_week_base=logged_28d_base / 4.0)
    usable = [v for v in vials if v.status != "discarded"]
    if not usable:
        return ref
    newest = max(usable, key=lambda v: v.id)
    ref.dim = newest.dim
    usable = [v for v in usable if v.dim == ref.dim]
    active = [v for v in usable if v.status in ACTIVE_STATUSES]

    pool = active or [newest]
    content = sum(v.content_base for v in pool)
    if content > 0:
        ref.cost_per_base = sum(v.landed_cents for v in pool) / content

    # Prefer an in-use vial's concentration, then any other active, then any.
    for v in sorted(active or usable, key=lambda v: (v.status != "in_use", -v.id)):
        if v.conc_per_ml:
            ref.conc_per_ml = v.conc_per_ml
            break

    ref.on_hand_base = sum(v.remaining_base for v in active)
    ref.typical_vial_base = newest.content_base or None
    ref.typical_vial_cents = newest.landed_cents
    return ref


# ---------------------------------------------------------------- protocols
@dataclass
class ItemInput:
    compound_id: int
    amount_value: float
    amount_unit: str
    freq_count: float
    freq_period: str  # "day" | "week" | "month" | "interval"


@dataclass
class ItemResult:
    compound_id: int | None
    compound_name: str
    warnings: list[str] = field(default_factory=list)
    ok: bool = False
    dim: str | None = None
    dose_base: float = 0.0
    doses_per_day: float = 0.0
    per_week_base: float = 0.0
    per_month_base: float = 0.0
    horizon_need_base: float = 0.0
    cost_per_dose: float | None = None
    cost_per_week: float | None = None
    cost_per_month: float | None = None
    horizon_cost: float | None = None
    on_hand_base: float = 0.0
    days_supply: float | None = None
    runout: date | None = None
    shortfall_base: float = 0.0
    vials_to_buy: int = 0
    buy_cents: float | None = None
    draw_ml: float | None = None
    syringe_marks: float | None = None
    actual_per_week_base: float | None = None


def doses_per_day(count: float, period: str) -> float:
    if count < 0:
        raise ValueError("Frequency can't be negative.")
    if period == "interval":
        if count <= 0:
            raise ValueError("The interval must be more than 0 days.")
        return 1.0 / count
    if period in PERIOD_DAYS:
        return count / PERIOD_DAYS[period]
    raise ValueError(f"Unknown frequency period '{period}'.")


def invalid_result(name: str, message: str, compound_id: int | None = None) -> ItemResult:
    return ItemResult(compound_id, name, warnings=[message])


def project_item(item: ItemInput, ref: CompoundRef, horizon_days: float,
                 today: date | None = None) -> ItemResult:
    today = today or date.today()
    res = ItemResult(item.compound_id, ref.name)
    try:
        unit = U.parse_unit(item.amount_unit)
        if item.amount_value < 0:
            raise ValueError("Amount can't be negative.")
        dpd = doses_per_day(item.freq_count, item.freq_period)
        dim = ref.dim or (unit.dim if unit.dim != "volume" else None)
        if dim is None:
            raise U.UnitError("No vials are on file for this compound yet, so a volume "
                              "can't be converted. Enter the amount as mass or IU.")
        dose_base = U.amount_to_vial_base(item.amount_value, item.amount_unit, dim,
                                          ref.conc_per_ml)
    except ValueError as exc:  # UnitError is a ValueError
        res.warnings.append(str(exc))
        return res

    res.ok, res.dim, res.dose_base, res.doses_per_day = True, dim, dose_base, dpd
    per_day = dose_base * dpd
    res.per_week_base = per_day * 7
    res.per_month_base = per_day * MONTH_DAYS
    res.horizon_need_base = per_day * horizon_days
    res.on_hand_base = ref.on_hand_base
    res.actual_per_week_base = ref.actual_per_week_base

    if ref.conc_per_ml and dose_base > 0:
        res.draw_ml = dose_base / ref.conc_per_ml
        res.syringe_marks = U.ml_to_syringe_units(res.draw_ml)

    if per_day > 0:
        res.days_supply = ref.on_hand_base / per_day
        if res.days_supply < 36_500:
            res.runout = today + timedelta(days=math.floor(res.days_supply + 1e-9))
    res.shortfall_base = max(res.horizon_need_base - ref.on_hand_base, 0.0)

    if ref.cost_per_base is not None:
        c = ref.cost_per_base
        res.cost_per_dose = dose_base * c
        res.cost_per_week = res.per_week_base * c
        res.cost_per_month = res.per_month_base * c
        res.horizon_cost = res.horizon_need_base * c
    else:
        res.warnings.append("No price on file, so costs can't be calculated.")

    if res.shortfall_base > 0 and ref.typical_vial_base:
        res.vials_to_buy = math.ceil(res.shortfall_base / ref.typical_vial_base - 1e-9)
        if ref.typical_vial_cents is not None:
            res.buy_cents = res.vials_to_buy * ref.typical_vial_cents
    return res


def totals(results: list[ItemResult]) -> dict[str, float]:
    def s(attr: str) -> float:
        return sum((getattr(r, attr) or 0.0) for r in results)
    return {
        "week": s("cost_per_week"),
        "month": s("cost_per_month"),
        "horizon": s("horizon_cost"),
        "buy": s("buy_cents"),
    }
