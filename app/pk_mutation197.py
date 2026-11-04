"""Fail-closed scenario mutation gates for SQLite-backed PK."""
from fastapi import HTTPException

from .pk_write177 import begin
from .pk_scenario_ops import scenario
from .pk_scenario_version import (
    snapshot,check,audit,version
)


def prepare(db,sid,expected):
    if not expected:
        raise HTTPException(
            428,'Scenario revision required'
        )

    begin(db)
    obj=scenario(db,sid)
    check(db,obj,expected)

    return obj,snapshot(db,obj)


def finish(db,obj,action,before):
    db.flush()
    db.expire(obj,['doses'])

    after=snapshot(db,obj)

    audit(
        db,obj.id,action,before,after
    )

    db.commit()

    return version(after)
