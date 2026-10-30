"""Transactional change audit helpers; call before the enclosing commit."""
import json
from datetime import date, datetime
from .models import ChangeAudit

def snapshot(obj, fields):
    result = {}
    for field in fields:
        value = getattr(obj, field)
        if isinstance(value, (date, datetime)):
            value = value.isoformat()
        result[field] = value
    return result

def record(db, kind, entity_id, action, before=None, after=None):
    db.add(ChangeAudit(entity_type=kind, entity_id=entity_id, action=action,
                       before_json=json.dumps(before or {}, default=str),
                       after_json=json.dumps(after or {}, default=str)))
