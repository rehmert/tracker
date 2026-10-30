"""Read-only supply ledger and orphan diagnostics (Stage 25)."""
import math
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .models import Supply, SupplyUsage, InventoryAdjustment, Purchase, Vial, DoseLog


def collect_inventory_health(db: Session):
    """Return (severity, explanation, review URL) tuples; never mutate stock."""
    findings = []
    supplies = list(db.scalars(select(Supply).order_by(Supply.id)))
    for s in supplies:
        if db.get(Purchase, s.purchase_id) is None:
            findings.append(('Error', f'Supply #{s.id} ({s.name}) references missing purchase #{s.purchase_id}.', '/supplies'))
        usages = list(db.scalars(select(SupplyUsage).where(SupplyUsage.supply_id == s.id)))
        adjustments = list(db.scalars(select(InventoryAdjustment).where(InventoryAdjustment.supply_id == s.id)))
        for u in usages:
            if not math.isfinite(u.amount) or u.amount <= 0:
                findings.append(('Error', f'Supply usage #{u.id} has invalid quantity.', '/consumption'))
            if u.vial_id is not None and db.get(Vial, u.vial_id) is None:
                findings.append(('Error', f'Supply usage #{u.id} references missing vial #{u.vial_id}.', '/consumption'))
            if u.dose_id is not None and db.get(DoseLog, u.dose_id) is None:
                findings.append(('Error', f'Supply usage #{u.id} references missing dose #{u.dose_id}.', '/consumption'))
        if not adjustments:
            # Only compare when the stock has never been reset by a physical count.
            if all(math.isfinite(x) for x in (s.purchased_qty, s.remaining_qty)) and all(math.isfinite(u.amount) for u in usages):
                expected = s.purchased_qty - sum(u.amount for u in usages)
                if not math.isclose(expected, s.remaining_qty, rel_tol=1e-8, abs_tol=1e-5):
                    findings.append(('Warning', f'Supply #{s.id} ({s.name}) balance differs from purchase minus recorded usage: expected {expected:.4f}, stored {s.remaining_qty:.4f}. Other stock operations may explain the difference; review before adjusting.', '/reconciliation'))
        else:
            for a in adjustments:
                if not all(math.isfinite(x) and x >= 0 for x in (a.previous_qty, a.counted_qty)):
                    findings.append(('Error', f'Supply adjustment #{a.id} has invalid stock values.', '/reconciliation'))
    for u in db.scalars(select(SupplyUsage).outerjoin(Supply, SupplyUsage.supply_id == Supply.id).where(Supply.id.is_(None))):
        findings.append(('Error', f'Supply usage #{u.id} references missing supply #{u.supply_id}.', '/consumption'))
    for a in db.scalars(select(InventoryAdjustment).outerjoin(Supply, InventoryAdjustment.supply_id == Supply.id).where(Supply.id.is_(None))):
        findings.append(('Error', f'Inventory adjustment #{a.id} references missing supply #{a.supply_id}.', '/reconciliation'))
    return findings
