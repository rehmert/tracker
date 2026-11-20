"""Stable BlendDose primary keys even when a historical withdrawal was deleted.

SQLite tables created before 711 use INTEGER PRIMARY KEY (not AUTOINCREMENT);
deleting the highest row can otherwise reuse that ID and mingle retained audit
records with a completely different physical withdrawal.

Call only AFTER acquiring BEGIN IMMEDIATE on the same SQLite session.
"""
from sqlalchemy import func, select

from .models import BlendDose, ChangeAudit


def next_blend_dose_id711(db) -> int:
    """Reserve a never-before-audited BlendDose ID under the caller's write lock."""
    current = db.scalar(select(func.max(BlendDose.id))) or 0
    audited = db.scalar(select(func.max(ChangeAudit.entity_id)).where(
        ChangeAudit.entity_type == "blend_dose",
    )) or 0
    return max(current, audited) + 1
