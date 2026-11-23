"""Reusable read-only list queries; no database schema changes."""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .models import Vial,Purchase,VIAL_STATUSES


def vial_listing(status='active',compound_id=None,coa=None):
    query=select(Vial)

    if compound_id is not None:
        query=query.where(
            Vial.compound_id==compound_id
        )

    if status=='active':
        query=query.where(
            Vial.status.in_(('sealed','in_use'))
        )
    elif status=='non_discarded':
        # Match the dashboard's no-COA count, including finished vials.
        query=query.where(Vial.status != 'discarded')
    elif status in VIAL_STATUSES:
        query=query.where(Vial.status==status)

    if coa == 'missing':
        # COAs may be legacy single links or the newer many-to-many links.
        # Use both association paths, consistent with Vial.all_coas.
        query=query.where(
            Vial.coa_id.is_(None),
            ~Vial.linked_coas.any(),
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
