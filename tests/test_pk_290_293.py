import sqlite3
import pytest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.inventory_lock import (
    reserve_inventory_write,
    require_inventory_write,
)
from app.idempotency import check,record,payload_hash


def test_concurrent_inventory_writer_conflict(tmp_path):
    path=tmp_path/'lock.db'

    engine=create_engine(
        f'sqlite:///{path}',
        connect_args={'timeout':.1}
    )

    Base.metadata.create_all(engine)

    blocker=sqlite3.connect(
        path,
        isolation_level=None
    )
    blocker.execute('BEGIN IMMEDIATE')

    try:
        with Session(engine) as db:
            with pytest.raises(HTTPException) as error:
                require_inventory_write(db)

            assert error.value.status_code==409
    finally:
        blocker.rollback()
        blocker.close()

    with Session(engine) as db:
        assert reserve_inventory_write(db)
        db.rollback()

    engine.dispose()


def test_durable_replay_and_payload_conflict(tmp_path):
    engine=create_engine(
        f'sqlite:///{tmp_path / "replay.db"}'
    )

    Base.metadata.create_all(engine)

    token='9c2ead2d-df17-4c27-98c0-4d4ae53563cf'
    payload={'b':2,'a':1}

    with Session(engine) as db:
        assert reserve_inventory_write(db)

        state,digest=check(
            db,token,'purchase_create',payload
        )

        assert state=='new'

        record(
            db,token,'purchase_create',digest
        )
        db.commit()

    with Session(engine) as db:
        assert check(
            db,token,'purchase_create',
            {'a':1,'b':2}
        )[0]=='replay'

        assert check(
            db,token,'purchase_create',
            {'a':9,'b':2}
        )[0]=='conflict'

    assert payload_hash(payload)==payload_hash({
        'a':1,'b':2
    })

    engine.dispose()
