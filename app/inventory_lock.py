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
