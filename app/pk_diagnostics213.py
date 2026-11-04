"""Read-only SQL aggregate diagnostics with bounded findings."""
from sqlalchemy import select,func,or_
from .models import Vial,DoseLog,ProtocolItem


def inspect(db,limit=100):
    if not 1<=limit<=200:
        raise ValueError(
            'Limit must be between 1 and 200'
        )

    counts={
        'vials_checked':db.scalar(
            select(func.count(Vial.id))
        ) or 0,
        'logs_checked':db.scalar(
            select(func.count(DoseLog.id))
        ) or 0,
        'protocol_items_checked':db.scalar(
            select(func.count(ProtocolItem.id))
        ) or 0
    }

    queries=[
        (
            'vial_content',
            select(Vial.id).where(
                or_(
                    Vial.content_value<=0,
                    Vial.content_value.is_(None)
                )
            )
        ),
        (
            'missing_vial',
            select(DoseLog.id)
            .outerjoin(
                Vial,DoseLog.vial_id==Vial.id
            )
            .where(Vial.id.is_(None))
        ),
        (
            'invalid_logged_amount',
            select(DoseLog.id).where(
                or_(
                    DoseLog.amount_base<=0,
                    DoseLog.amount_base.is_(None)
                )
            )
        ),
        (
            'unexpected_log_kind',
            select(DoseLog.id).where(
                DoseLog.kind.notin_(['dose','waste'])
            )
        ),
        (
            'invalid_protocol_amount',
            select(ProtocolItem.id).where(
                or_(
                    ProtocolItem.amount_value<=0,
                    ProtocolItem.amount_value.is_(None)
                )
            )
        )
    ]

    findings=[]

    for kind,query in queries:
        remaining=limit-len(findings)

        if remaining==0:
            break

        ids=db.scalars(
            query.limit(remaining+1)
        ).all()

        for id_ in ids[:remaining]:
            findings.append({
                'type':kind,
                'id':id_
            })

        if len(ids)>remaining:
            break

    return {
        'read_only':True,
        **counts,
        'findings':findings,
        'limit':limit,
        'truncated':len(findings)>=limit
    }
