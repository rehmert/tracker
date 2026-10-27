"""BAC-water-only inventory entry; quantities are stored as total milliliters."""
import math
from .models import Supply


def make_bac_water_supply(*, purchase_id, vial_count, ml_per_vial, name='', price_per_vial_cents=None, total_line_cents=None, notes=''):
    if isinstance(vial_count, bool) or not isinstance(vial_count, int) or not 1 <= vial_count <= 100000:
        raise ValueError('Number of BAC water vials must be a positive whole number.')
    if not math.isfinite(ml_per_vial) or not 0 < ml_per_vial <= 1000:
        raise ValueError('BAC water volume per vial must be between 0 and 1,000 mL.')
    if price_per_vial_cents is not None and total_line_cents is not None:
        raise ValueError('Enter either price per vial or total line cost, not both.')
    for label, value in [('Price per vial', price_per_vial_cents), ('Total line cost', total_line_cents)]:
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise ValueError(f'{label} must be a nonnegative amount.')
    line_cents = total_line_cents if total_line_cents is not None else (price_per_vial_cents or 0) * vial_count
    total = vial_count * ml_per_vial
    if total > 1000000:
        raise ValueError('Total BAC water inventory exceeds the supported limit.')
    return Supply(purchase_id=purchase_id, name=name.strip() or f'BAC water ({ml_per_vial:g} mL vial)',
                  kind='bac_water', compound_id=None, purchased_qty=total, remaining_qty=total,
                  unit_price_cents=round(line_cents / total), bulk_pack_count=vial_count,
                  bulk_units_per_pack=ml_per_vial, bulk_total_cents=line_cents, notes=notes.strip())
