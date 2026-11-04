"""Revision-protected PK edits and transactional audit snapshots."""
from fastapi import HTTPException
from . import pk_scenario_version as ver


def required(db, obj, expected):
    if not expected:
        raise HTTPException(
            428,
            'Refresh scenario before saving (missing revision)'
        )
    ver.check(db, obj, expected)


def changed(db, obj, action, before):
    db.flush()
    ver.audit(
        db, obj.id, action,
        before, ver.snapshot(db, obj)
    )
