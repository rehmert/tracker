"""Projection-only exclusions, shared by calendar and dashboard."""
from sqlalchemy import select
from .models import ProjectionExclusion


def exclusions_for(db, item_ids):
    ids = list(item_ids)
    if not ids:
        return {}
    result = {}
    for row in db.scalars(select(ProjectionExclusion).where(ProjectionExclusion.protocol_item_id.in_(ids))):
        result.setdefault(row.protocol_item_id, []).append(row)
    return result


def excluded(rules, item_id, day):
    return any((r.scope == 'once' and r.scheduled_on == day) or
               (r.scope == 'onward' and day >= r.scheduled_on)
               for r in rules.get(item_id, ()))
