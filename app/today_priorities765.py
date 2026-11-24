"""Release 765: read-only, workspace-scoped daily action counts and examples.

No cached medical records, data writes, or broad unscoped records.
"""
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload, Session

from .models import Vial


def missing_coa_count765(db: Session) -> int:
    """Same non-discarded + both-COA-associations definition as Dashboard."""
    return int(db.scalar(
        select(func.count(Vial.id)).where(
            Vial.status != "discarded",
            Vial.coa_id.is_(None),
            ~Vial.linked_coas.any(),
        )
    ) or 0)


def passed_date_examples765(db: Session, today: date, limit: int = 4):
    """Short exact-record drilldown matching the Today date-attention scope."""
    if limit < 1 or limit > 10:
        raise ValueError("Limited to 1–10 read-only examples")
    return list(db.scalars(
        select(Vial).where(
            Vial.status.in_(("sealed", "in_use")),
            Vial.closed_on.is_(None),
            or_(
                Vial.expires_on < today,
                Vial.beyond_use_on < today,
            ),
        )
        .options(selectinload(Vial.compound))
        .order_by(Vial.id.desc())
        .limit(limit)
    ))
