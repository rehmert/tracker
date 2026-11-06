"""Release 425: separately logged water in US fluid ounces."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import text

WATER_TARGET_OZ = 140
MAX_ENTRY_OZ = Decimal("256")
PRECISION = Decimal("0.01")


def parse_ounces(raw):
    try:
        value = Decimal(str(raw).strip())

        if (
            not value.is_finite()
            or value <= 0
            or value > MAX_ENTRY_OZ
        ):
            raise ValueError("Water quantity out of range")

        value = value.quantize(
            PRECISION,
            rounding=ROUND_HALF_UP,
        )

        if value <= 0:
            raise ValueError("Water quantity too small")

        return float(value)

    except (InvalidOperation, ValueError, TypeError, OverflowError):
        raise ValueError(
            "Enter a water quantity greater than zero "
            "and no more than 256 fl oz"
        ) from None


def init_water_schema(db_engine):
    """Create an independent water table, preserving food data."""
    with db_engine.begin() as db:
        db.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS tracker_water_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                logged_on TEXT NOT NULL,
                ounces REAL NOT NULL
                    CHECK(ounces > 0 AND ounces <= 256),
                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.exec_driver_sql("""
            CREATE INDEX IF NOT EXISTS idx_tracker_water_day425
            ON tracker_water_entries(logged_on, id)
        """)


def water_report(day, db_engine):
    """Return only explicitly recorded water for a selected day."""
    with db_engine.connect() as db:
        rows = db.execute(text("""
            SELECT id, ounces, created_at
            FROM tracker_water_entries
            WHERE logged_on=:day
            ORDER BY id DESC
        """), {"day": day}).mappings().all()

    entries = [dict(row) for row in rows]
    total = round(sum(item["ounces"] for item in entries), 2)

    return {
        "entries": entries,
        "count": len(entries),
        "total": total,
        "target": WATER_TARGET_OZ,
        "remaining": round(max(0, WATER_TARGET_OZ - total), 2),
        "over": round(max(0, total - WATER_TARGET_OZ), 2),
        "percent": min(
            100,
            round(total * 100 / WATER_TARGET_OZ),
        ),
    }
