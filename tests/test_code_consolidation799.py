from sqlalchemy import select
from sqlalchemy.dialects import sqlite
from sqlalchemy.orm import selectinload

from app.models import Protocol, ProtocolItem
from app.protocol_queries import protocol_read_query


def test_protocol_query_preserves_active_filter_and_order():
    for active in (False, True):
        expected = select(Protocol).options(
            selectinload(Protocol.items).selectinload(ProtocolItem.compound)
        )
        if active:
            expected = expected.where(Protocol.is_active.is_(True))
        for order in (Protocol.name, Protocol.updated_at.desc()):
            actual = protocol_read_query(active_only=active).order_by(order)
            assert str(actual.compile(dialect=sqlite.dialect())) == str(
                expected.order_by(order).compile(dialect=sqlite.dialect())
            )
            assert [str(option.path) for option in actual._with_options] == [
                str(option.path) for option in expected._with_options
            ]
            assert actual._with_options[0].context[-1].strategy == (
                ("lazy", "selectin"),
            )


def test_protocol_query_is_independent_per_call():
    assert protocol_read_query() is not protocol_read_query()
    assert not protocol_read_query().whereclause is not None
    assert protocol_read_query(active_only=True).whereclause is not None
