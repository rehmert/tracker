from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.idempotency import check, record, new_token

def test_durable_replay_and_conflict():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    token = new_token()
    with Session(engine) as db:
        state, digest = check(db, token, 'dose_create', {'amount': 1})
        assert state == 'new'
        record(db, token, 'dose_create', digest)
        db.commit()
    with Session(engine) as db:
        assert check(db, token, 'dose_create', {'amount': 1})[0] == 'replay'
        assert check(db, token, 'dose_create', {'amount': 2})[0] == 'conflict'
        assert check(db, 'invalid', 'dose_create', {})[0] == 'invalid'
