"""Read-only diagnostics; never modify dose or inventory data."""
from math import isfinite
from sqlalchemy import select

from .models import Vial,DoseLog,ProtocolItem


def inspect(db):
    problems=[]

    vials=list(db.scalars(select(Vial)))
    vial_by_id={v.id:v for v in vials}
    entries=list(db.scalars(select(DoseLog)))

    for vial in vials:
        if (
            not isfinite(vial.content_value)
            or vial.content_value<=0
        ):
            problems.append({
                'type':'vial_content',
                'id':vial.id
            })

    for log in entries:
        if log.vial_id not in vial_by_id:
            problems.append({
                'type':'missing_vial',
                'id':log.id
            })

        if (
            not isfinite(log.amount_base)
            or log.amount_base<=0
        ):
            problems.append({
                'type':'invalid_logged_amount',
                'id':log.id
            })

        if log.kind not in ('dose','waste'):
            problems.append({
                'type':'unexpected_log_kind',
                'id':log.id
            })

    items=list(db.scalars(select(ProtocolItem)))

    for item in items:
        if (
            not isfinite(item.amount_value)
            or item.amount_value<=0
        ):
            problems.append({
                'type':'invalid_protocol_amount',
                'id':item.id
            })

    return {
        'read_only':True,
        'vials_checked':len(vials),
        'logs_checked':len(entries),
        'protocol_items_checked':len(items),
        'findings':problems
    }
