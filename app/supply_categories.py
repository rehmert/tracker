import math
from sqlalchemy import select
from .models import SupplyCategory

DEFAULTS = (
    ("bac_water", "BAC water", "mL"),
    ("pill", "Pills / capsules", "count"),
    ("needle", "Needles", "count"),
    ("syringe", "Syringes", "count"),
    ("empty_vial", "Sterile empty vials", "count"),
    ("pen_cartridge", "Injection pen cartridges", "count"),
    ("swab", "Alcohol swabs", "count"),
    ("other_supply", "Other disposables", "count"),
)

def ensure_categories(db):
    found = {c.key: c for c in db.scalars(select(SupplyCategory)).all()}
    for key, label, unit in DEFAULTS:
        if key not in found:
            db.add(SupplyCategory(key=key, label=label, unit=unit))
    db.commit()
    return list(db.scalars(select(SupplyCategory).order_by(SupplyCategory.label)))

def validate_supply(db, kind, quantity, previous=None):
    category = db.scalar(select(SupplyCategory).where(SupplyCategory.key == kind))
    if category is None or not math.isfinite(quantity) or not 0 < quantity <= 1000000:
        raise ValueError("Choose a valid category and a positive quantity.")
    if category.unit == "count" and not float(quantity).is_integer():
        raise ValueError("Quantity must be a whole number for this category.")
    if previous and previous != kind:
        raise ValueError("Cannot change category after usage has been recorded.")
    return category
