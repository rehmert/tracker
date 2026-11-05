"""SQLite inventory write reservation, acquired before reading mutable stock."""
from sqlalchemy.exc import OperationalError


def reserve_inventory_write(db):
    """Return False on SQLite contention; caller must roll back on failure.

    BEGIN IMMEDIATE must be the first statement in this session transaction.
    It serializes writers; this is not a cross-database lock.
    """
    try:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        return True
    except OperationalError:
        db.rollback()
        return False


def require_inventory_write(db):
    """Acquire the SQLite write reservation or report contention."""
    from fastapi import HTTPException

    if not reserve_inventory_write(db):
        raise HTTPException(
            409,
            "Inventory is busy. Please retry."
        )
