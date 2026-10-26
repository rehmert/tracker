"""Explicitly selected supplies; no automatic consumption or dosing decisions."""
from collections import Counter
from fastapi import Request
from sqlalchemy import select
from .models import Supply, SupplyCategory, SupplyUsage


def available(db):
    return list(db.scalars(select(Supply).where(Supply.remaining_qty > 0).order_by(Supply.name, Supply.id)))


async def selections(request: Request, db):
    form = await request.form()
    chosen = Counter()
    for raw in form.getlist("supply_id_used"):
        try:
            sid = int(raw)
            qty = float(form.get(f"supply_qty_{sid}", "1"))
        except (ValueError, TypeError):
            raise ValueError("Invalid supply selection or quantity.")
        if qty <= 0 or not __import__('math').isfinite(qty):
            raise ValueError("Supply quantity must be positive and finite.")
        chosen[sid] += qty
    result = []
    for sid, qty in chosen.items():
        item = db.get(Supply, sid)
        if item is None or qty > item.remaining_qty + 1e-9:
            raise ValueError("Selected supplies exceed available stock.")
        cat = db.query(SupplyCategory).filter_by(key=item.kind).first()
        if cat and cat.unit == "count" and not qty.is_integer():
            raise ValueError("Counted disposables must use whole quantities.")
        result.append((item, qty))
    return result


def deduct(db, selected, *, dose_id=None, vial_id=None):
    usages = []
    for item, qty in selected:
        item.remaining_qty -= qty
        usage = SupplyUsage(supply_id=item.id, amount=qty, dose_id=dose_id, vial_id=vial_id)
        db.add(usage)
        usages.append(usage)
    return usages


def restore_dose(db, did):
    for usage in db.scalars(select(SupplyUsage).where(SupplyUsage.dose_id == did)).all():
        item = db.get(Supply, usage.supply_id)
        if item: item.remaining_qty += usage.amount
        db.delete(usage)
