"""Shared protocol read query; callers retain their scoped session and ordering."""
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .models import Protocol, ProtocolItem


def protocol_read_query(*, active_only=False):
    """Load protocol items and compounds without per-row lazy queries."""
    query = select(Protocol).options(
        selectinload(Protocol.items).selectinload(ProtocolItem.compound)
    )
    if active_only:
        query = query.where(Protocol.is_active.is_(True))
    return query
