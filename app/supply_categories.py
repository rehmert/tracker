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
    """Seed defaults atomically, even when multiple requests initialize them."""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from sqlalchemy.exc import IntegrityError
    from .inventory_lock import reserve_inventory_write

    # SQLite writer reservation prevents simultaneous initializers from racing.
    # Never commit an unrelated pending transaction in this helper.
    if db.new or db.dirty or db.deleted:
        raise RuntimeError("Seed supply categories before modifying session objects")
    if not reserve_inventory_write(db):
        raise RuntimeError("Supply categories are busy; please retry")
    try:
        for key, label, unit in DEFAULTS:
            db.execute(sqlite_insert(SupplyCategory).values(key=key, label=label, unit=unit)
                       .on_conflict_do_nothing(index_elements=["key"]))
        db.commit()
    except Exception:
        db.rollback()
        raise
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
