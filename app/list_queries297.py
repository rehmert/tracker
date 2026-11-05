"""Reusable read-only list queries; no database schema changes."""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .models import Vial,Purchase,VIAL_STATUSES


def vial_listing(status='active',compound_id=None):
    query=select(Vial)

    if compound_id is not None:
        query=query.where(
            Vial.compound_id==compound_id
        )

    if status=='active':
        query=query.where(
            Vial.status.in_(('sealed','in_use'))
        )
    elif status in VIAL_STATUSES:
        query=query.where(
            Vial.status==status
        )

    return query.order_by(Vial.id.desc())


def purchase_listing():
    return (
        select(Purchase)
        .options(
            selectinload(Purchase.vials),
            selectinload(Purchase.supplies)
        )
        .order_by(
            Purchase.purchased_on.desc(),
            Purchase.id.desc()
        )
    )
