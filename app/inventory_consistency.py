"""Read-only inventory diagnostics. Never automatically change stock.

The supply ledger is only conclusive when all historical stock movements are
represented by SupplyUsage and InventoryAdjustment rows. Historical manual edits,
imports and deleted events may cause false discrepancies.
"""
from collections import defaultdict
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
    # Bulk read each ledger once. Preserve existing Python arithmetic
    # and Finding classification without changing inventory records.
    usages_by_supply = defaultdict(list)
    for usage in db.scalars(
        select(SupplyUsage).order_by(SupplyUsage.id)
    ):
        usages_by_supply[usage.supply_id].append(usage)

    adjustments_by_supply = defaultdict(list)
    for adjustment in db.scalars(
        select(InventoryAdjustment).order_by(InventoryAdjustment.id)
    ):
        adjustments_by_supply[adjustment.supply_id].append(adjustment)

    doses_by_vial = defaultdict(list)
    for dose in db.scalars(
        select(DoseLog).order_by(DoseLog.id)
    ):
        doses_by_vial[dose.vial_id].append(dose)

    transfers_by_vial = defaultdict(list)
    for transfer in db.scalars(
        select(BlendComponent).order_by(BlendComponent.id)
    ):
        transfers_by_vial[transfer.source_vial_id].append(transfer)
    for supply in db.scalars(select(Supply).order_by(Supply.id)):
        qty = float(supply.remaining_qty)
        purchased = float(supply.purchased_qty)
        if not all(isfinite(v) for v in (qty, purchased)):
            findings.append(Finding('supply', supply.id, 'nonfinite', 'Non-finite supply quantity'))
            continue
        if qty < -TOLERANCE or purchased < -TOLERANCE:
            findings.append(Finding('supply', supply.id, 'negative', 'Negative supply quantity', qty))
        usages = usages_by_supply[supply.id]
        adjustments = adjustments_by_supply[supply.id]
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
        doses = doses_by_vial[vial.id]
        transfers = transfers_by_vial[vial.id]
        consumed = sum(float(d.amount_base) for d in doses) + sum(float(t.transferred_base) for t in transfers)
        if not isfinite(consumed):
            findings.append(Finding('vial', vial.id, 'nonfinite_consumption', 'Non-finite vial consumption'))
        elif consumed < -TOLERANCE:
            findings.append(Finding('vial', vial.id, 'negative_consumption', 'Negative total vial consumption', consumed))
        # Vial potency and unit conversions can depend on COA data; avoid claiming
        # a definitive stock balance without the same calculations as the UI.
    return findings
