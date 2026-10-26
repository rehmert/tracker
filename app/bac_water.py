"""BAC-water-only inventory entry; quantities are stored as total milliliters."""
import math
from .models import Supply


def make_bac_water_supply(*, purchase_id, vial_count, ml_per_vial, name='', price_per_vial_cents=0, notes=''):
    if isinstance(vial_count, bool) or not isinstance(vial_count, int) or not 1 <= vial_count <= 100000:
        raise ValueError('Number of BAC water vials must be a positive whole number.')
    if not math.isfinite(ml_per_vial) or not 0 < ml_per_vial <= 1000:
        raise ValueError('BAC water volume per vial must be between 0 and 1,000 mL.')
    if isinstance(price_per_vial_cents, bool) or not isinstance(price_per_vial_cents, int) or price_per_vial_cents < 0:
        raise ValueError('Price per vial must not be negative.')
    total = vial_count * ml_per_vial
    if total > 1000000:
        raise ValueError('Total BAC water inventory exceeds the supported limit.')
    return Supply(purchase_id=purchase_id, name=name.strip() or f'BAC water ({ml_per_vial:g} mL vial)',
                  kind='bac_water', compound_id=None, purchased_qty=total, remaining_qty=total,
                  unit_price_cents=round(price_per_vial_cents / ml_per_vial), bulk_pack_count=vial_count,
                  bulk_units_per_pack=ml_per_vial, bulk_total_cents=price_per_vial_cents * vial_count, notes=notes.strip())
