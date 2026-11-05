"""Batch preparation detail queries while retaining ORM data objects."""
from sqlalchemy import select
from .models import (
    PreparationEvent,PreparationSupply,SupplyUsage,Supply
)


def load_preparations(db,vial_id):
    events=list(db.scalars(
        select(PreparationEvent)
        .where(PreparationEvent.vial_id==vial_id)
        .order_by(PreparationEvent.id.desc())
    ))

    result={event.id:[] for event in events}
    if not events:
        return events,result

    links=list(db.scalars(
        select(PreparationSupply)
        .where(
            PreparationSupply.event_id.in_(
                [event.id for event in events]
            )
        )
        .order_by(PreparationSupply.id)
    ))

    if not links:
        return events,result

    usages={
        item.id:item for item in db.scalars(
            select(SupplyUsage).where(
                SupplyUsage.id.in_(
                    {link.usage_id for link in links}
                )
            )
        )
    }

    ids={u.supply_id for u in usages.values()}
    supplies={
        item.id:item for item in db.scalars(
            select(Supply).where(Supply.id.in_(ids))
        )
    } if ids else {}

    for link in links:
        usage=usages.get(link.usage_id)
        result[link.event_id].append((
            usage,
            supplies.get(usage.supply_id) if usage else None
        ))

    return events,result
