"""Read-only, descriptive inventory forecasts; never suggests a dose or changes records."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from math import isfinite
from sqlalchemy import select
from .models import Vial, DoseLog, Supply, SupplyUsage
from .services import vial_views


def _estimate(remaining, amount_used, days, today):
    if not isfinite(remaining) or remaining < 0 or not isfinite(amount_used) or amount_used <= 0:
        return None, None
    days_left = remaining * days / amount_used
    if not isfinite(days_left):
        return None, None
    return days_left, today + timedelta(days=min(int(days_left), 365000))


def forecast_inventory(db, today: date | None = None, window_days: int = 90):
    if window_days not in (30, 90, 180):
        raise ValueError('Unsupported history window')
    today = today or date.today()
    start = datetime.combine(today - timedelta(days=window_days), datetime.min.time())
    end = datetime.combine(today + timedelta(days=1), datetime.min.time())
    vials = list(db.scalars(select(Vial)))
    views = vial_views(db, vials)
    vial_by_id = {v.id: v for v in vials}
    inventory = defaultdict(float)
    names = {}
    for vial in vials:
        if vial.status not in ('sealed', 'in_use'):
            continue
        if (vial.expires_on and vial.expires_on < today) or (vial.beyond_use_on and vial.beyond_use_on < today):
            continue
        view = views[vial.id]
        key = (vial.compound_id, view.dim)
        inventory[key] += max(0.0, view.remaining_base)
        names[key] = vial.compound.name
    consumed = defaultdict(float)
    for log in db.scalars(select(DoseLog).where(DoseLog.taken_at >= start, DoseLog.taken_at < end, DoseLog.kind == 'dose')):
        vial = vial_by_id.get(log.vial_id)
        if vial and isfinite(log.amount_base) and log.amount_base > 0:
            key = (vial.compound_id, views[vial.id].dim)
            consumed[key] += log.amount_base
            names[key] = vial.compound.name
    units = {'mass': 'mcg', 'iu': 'IU', 'volume': 'mL'}
    compounds = []
    for key in sorted(inventory, key=lambda k: (names[k].casefold(), k[1])):
        remaining = inventory[key]
        usage = consumed[key]
        days_left, depletion = _estimate(remaining, usage, window_days, today)
        compounds.append(dict(name=names[key], remaining=remaining, used=usage, unit=units.get(key[1], key[1]),
                              days_left=days_left, depletion=depletion,
                              warning=days_left is not None and days_left <= 21))
    supplies = list(db.scalars(select(Supply)))
    supply_used = defaultdict(float)
    for usage in db.scalars(select(SupplyUsage).where(SupplyUsage.created_at >= start, SupplyUsage.created_at < end)):
        if isfinite(usage.amount) and usage.amount > 0:
            supply_used[usage.supply_id] += usage.amount
    supply_rows = []
    for supply in sorted(supplies, key=lambda s: (s.name.casefold(), s.id)):
        remaining = max(0.0, supply.remaining_qty or 0.0)
        used = supply_used[supply.id]
        days_left, depletion = _estimate(remaining, used, window_days, today)
        supply_rows.append(dict(name=supply.name, id=supply.id, remaining=remaining, used=used,
                                days_left=days_left, depletion=depletion,
                                warning=days_left is not None and days_left <= 21))
    return compounds, supply_rows
