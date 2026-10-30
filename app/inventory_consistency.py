"""Read-only inventory diagnostics. Never automatically change stock.

The supply ledger is only conclusive when all historical stock movements are
represented by SupplyUsage and InventoryAdjustment rows. Historical manual edits,
imports and deleted events may cause false discrepancies.
"""
from dataclasses import dataclass
from math import isfinite
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Supply, SupplyUsage, InventoryAdjustment, Vial, DoseLog, BlendComponent

TOLERANCE = 1e-5

@dataclass(frozen=True)
class Finding:
    category: str
    record_id: int
    code: str
    message: str
    observed: float | None = None
    expected: float | None = None


def inspect_inventory(db: Session) -> list[Finding]:
    """Return findings without issuing any INSERT, UPDATE or DELETE."""
    findings: list[Finding] = []
    for supply in db.scalars(select(Supply).order_by(Supply.id)):
        qty = float(supply.remaining_qty)
        purchased = float(supply.purchased_qty)
        if not all(isfinite(v) for v in (qty, purchased)):
            findings.append(Finding('supply', supply.id, 'nonfinite', 'Non-finite supply quantity'))
            continue
        if qty < -TOLERANCE or purchased < -TOLERANCE:
            findings.append(Finding('supply', supply.id, 'negative', 'Negative supply quantity', qty))
        usages = list(db.scalars(select(SupplyUsage).where(SupplyUsage.supply_id == supply.id)))
        adjustments = list(db.scalars(select(InventoryAdjustment).where(InventoryAdjustment.supply_id == supply.id).order_by(InventoryAdjustment.id)))
        if any(not isfinite(float(u.amount)) or float(u.amount) < 0 for u in usages):
            findings.append(Finding('supply', supply.id, 'invalid_usage', 'Invalid supply usage amount'))
            continue
        if any(not isfinite(float(a.previous_qty)) or not isfinite(float(a.counted_qty)) for a in adjustments):
            findings.append(Finding('supply', supply.id, 'invalid_adjustment', 'Invalid reconciliation amount'))
            continue
        expected = purchased - sum(float(u.amount) for u in usages) + sum(float(a.counted_qty - a.previous_qty) for a in adjustments)
        if abs(qty - expected) > TOLERANCE:
            findings.append(Finding('supply', supply.id, 'ledger_mismatch',
                                    'Stored balance differs from available transaction history; review historical edits/imports',
                                    qty, expected))
    for vial in db.scalars(select(Vial).order_by(Vial.id)):
        doses = db.scalars(select(DoseLog).where(DoseLog.vial_id == vial.id))
        transfers = db.scalars(select(BlendComponent).where(BlendComponent.source_vial_id == vial.id))
        consumed = sum(float(d.amount_base) for d in doses) + sum(float(t.transferred_base) for t in transfers)
        if not isfinite(consumed):
            findings.append(Finding('vial', vial.id, 'nonfinite_consumption', 'Non-finite vial consumption'))
        elif consumed < -TOLERANCE:
            findings.append(Finding('vial', vial.id, 'negative_consumption', 'Negative total vial consumption', consumed))
        # Vial potency and unit conversions can depend on COA data; avoid claiming
        # a definitive stock balance without the same calculations as the UI.
    return findings
