"""Transactional management of hypothetical PK scenario doses."""
import hashlib
import json
from datetime import datetime, timedelta
from math import isfinite

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from .models import PkScenario, PkPlannedDose, ChangeAudit


class SequenceInput(BaseModel):
    start_at: datetime
    amount_mg: float = Field(gt=0, le=10000)
    interval_days: float = Field(ge=.125, le=90)
    count: int = Field(ge=1, le=200)


class DeleteInput(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)
    expected_version: str = Field(min_length=64, max_length=64)


class RestoreInput(BaseModel):
    audit_id: int = Field(gt=0)
    expected_version: str = Field(min_length=64, max_length=64)


def scenario(db, sid):
    obj=db.get(PkScenario,sid)
    if obj is None:
        raise HTTPException(404,'Scenario not found')
    return obj


def rows(db,sid):
    return list(db.scalars(
        select(PkPlannedDose)
        .where(PkPlannedDose.scenario_id==sid)
        .order_by(
            PkPlannedDose.planned_at,
            PkPlannedDose.id
        )
    ))


def fingerprint(items):
    values=[
        (x.id,x.planned_at.isoformat(),x.amount_mg)
        for x in items
    ]
    payload=json.dumps(values,separators=(',',':'))
    return hashlib.sha256(payload.encode()).hexdigest()


def state(db,sid):
    scenario(db,sid)
    items=rows(db,sid)
    return {
        'version':fingerprint(items),
        'count':len(items)
    }


def preview(data):
    if not all(isfinite(v) for v in (
        data.amount_mg,data.interval_days
    )):
        raise HTTPException(400,'Invalid numeric input')

    return [
        {
            'planned_at':(
                data.start_at+
                timedelta(days=i*data.interval_days)
            ).isoformat(),
            'amount_mg':data.amount_mg
        }
        for i in range(data.count)
    ]


def create_many(db,sid,data):
    scenario(db,sid)
    batch=preview(data)

    dates=[
        datetime.fromisoformat(x['planned_at'])
        for x in batch
    ]

    existing={
        x.planned_at for x in rows(db,sid)
    }

    if (
        len(set(dates))!=len(dates)
        or any(x in existing for x in dates)
    ):
        raise HTTPException(
            409,'Overlapping hypothetical dose timestamps'
        )

    for entry,at in zip(batch,dates):
        db.add(PkPlannedDose(
            scenario_id=sid,
            planned_at=at,
            amount_mg=entry['amount_mg']
        ))

    db.commit()
    return {'created':len(batch)}


def delete_many(db,sid,data):
    scenario(db,sid)
    items=rows(db,sid)

    if fingerprint(items)!=data.expected_version:
        raise HTTPException(
            409,'Scenario changed; reload before deleting'
        )

    if len(set(data.ids))!=len(data.ids):
        raise HTTPException(400,'Duplicate dose IDs')

    chosen=[
        x for x in items
        if x.id in set(data.ids)
    ]

    if len(chosen)!=len(data.ids):
        raise HTTPException(
            409,'One or more doses no longer exist'
        )

    snapshot=[
        {
            'planned_at':x.planned_at.isoformat(),
            'amount_mg':x.amount_mg
        }
        for x in chosen
    ]

    for item in chosen:
        db.delete(item)

    db.flush()
    after=fingerprint(rows(db,sid))

    audit=ChangeAudit(
        entity_type='pk_scenario',
        entity_id=sid,
        action='bulk_delete',
        before_json=json.dumps(snapshot),
        after_json=json.dumps({'version':after})
    )

    db.add(audit)
    db.commit()

    return {
        'deleted':len(chosen),
        'audit_id':audit.id,
        'version':after
    }


def restore(db,sid,data):
    scenario(db,sid)
    audit=db.get(ChangeAudit,data.audit_id)

    if (
        audit is None
        or audit.entity_type!='pk_scenario'
        or audit.entity_id!=sid
        or audit.action!='bulk_delete'
    ):
        raise HTTPException(
            404,'Undo operation unavailable'
        )

    latest=db.scalar(
        select(ChangeAudit)
        .where(
            ChangeAudit.entity_type=='pk_scenario',
            ChangeAudit.entity_id==sid,
            ChangeAudit.action=='bulk_delete'
        )
        .order_by(ChangeAudit.id.desc())
    )

    if latest is None or latest.id!=audit.id:
        raise HTTPException(
            409,'Newer deletion exists; undo unavailable'
        )

    current=fingerprint(rows(db,sid))

    if (
        current!=data.expected_version
        or current!=json.loads(
            audit.after_json
        )['version']
    ):
        raise HTTPException(
            409,'Scenario changed since deletion'
        )

    entries=json.loads(audit.before_json)

    for entry in entries:
        db.add(PkPlannedDose(
            scenario_id=sid,
            planned_at=datetime.fromisoformat(
                entry['planned_at']
            ),
            amount_mg=entry['amount_mg']
        ))

    audit.action='bulk_restored'
    db.commit()

    return {'restored':len(entries)}
